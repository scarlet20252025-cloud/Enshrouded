r"""Find the SendEventEx (0x140954250) dispatcher that the tame handler calls.

The tame handler at 0x14047d761 calls SendEventEx(rcx=ctx, edx=?, r8d=entityId)
right after GetCtx. Reading SendEventEx's prologue and its own callers tells us
whether it is a public "push this event" entry point we can call ourselves.
"""
import struct
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def dis(rva, n):
    va = S.IMAGE_BASE + rva
    r = subprocess.run(
        [OBJDUMP, "-d", "--start-address=%d" % va, "--stop-address=%d" % (va + n), EXE],
        capture_output=True, text=True, errors="replace")
    return (r.stdout or r.stderr).splitlines()


def callers_of(data, secs, want):
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    out = []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            if tlo + (i - lo) + 5 + rel == want:
                out.append(tlo + (i - lo))
    return out


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)

    for rva, what in [
        (0x954250, "SendEventEx (called by the tame handler)"),
        (0x9B2E40, "ResolveEnt (called right before SendEventEx)"),
        (0x9B8030, "called after the tame write (component store lookup?)"),
        (0x9C5DF0, "called in the handler preamble"),
    ]:
        want = S.IMAGE_BASE + rva
        cs = callers_of(data, secs, want)
        print("=" * 76)
        print("=== %s  rva=%#x   callers=%d" % (what, rva, len(cs)))
        r = S.enclosing(funcs, want)
        if r:
            print("    func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0]))
        print("=" * 76)
        for c in cs[:25]:
            rr = S.enclosing(funcs, c)
            fn = ("func rva=%#x size=%d" % (rr[0] - S.IMAGE_BASE, rr[1] - rr[0])) if rr else "?"
            print("   caller rva=%#x  %s" % (c - S.IMAGE_BASE, fn))

    print()
    print("=" * 76)
    print("=== SendEventEx prologue rva=0x954250 ===")
    print("=" * 76)
    for ln in dis(0x954250, 220):
        print(ln)


if __name__ == "__main__":
    main()
