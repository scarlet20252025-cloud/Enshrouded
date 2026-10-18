r"""Map the tame handler's actual entry by scanning backwards for the prologue.

0x47d5bc begins mid-instruction-sequence (saving rdi/r12/r13/r14/r15 to stack
without a `push`/`sub rsp`), so the real function starts earlier and 0x47d5bc
is an internal label. Walk backwards through .pdata to find the function that
CONTAINS 0x47d5bc and print from its start.
"""
import struct
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    target = S.IMAGE_BASE + 0x47D5BC

    # Find the pdata entry whose range covers target.
    cover = None
    for b, e in funcs:
        if b <= target < e:
            cover = (b, e)
            break
    print("pdata entry containing 0x47d5bc: %s" % (
        ("rva=%#x..%#x size=%d" % (cover[0] - S.IMAGE_BASE, cover[1] - S.IMAGE_BASE,
                                   cover[1] - cover[0])) if cover else "none"))

    # The handler's own pdata says size 577 starting exactly at 0x47d5bc, so it
    # IS a function start. Then who reaches it? Only a jump, not a call.
    # Scan for rel32 JUMPS (E9) to it.
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    jmp = []
    call = []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == target:
                (jmp if data[i] == 0xE9 else call).append(insn)
    print("E9 jumps to it: %d" % len(jmp))
    for c in jmp:
        r = S.enclosing(funcs, c)
        print("   jmp rva=%#x  %s" % (
            c - S.IMAGE_BASE,
            ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))
    print("E8 calls to it: %d" % len(call))

    # Disassemble backwards: print 0x200 bytes before 0x47d5bc.
    print("\n=== bytes before 0x47d5bc ===")
    start = S.IMAGE_BASE + 0x47D5BC - 0x180
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % start,
                        "--stop-address=%d" % (S.IMAGE_BASE + 0x47D5BC + 0x40), EXE],
                       capture_output=True, text=True, errors="replace")
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
