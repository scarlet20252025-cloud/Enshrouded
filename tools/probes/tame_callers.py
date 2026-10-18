r"""Find callers of the tame handler's REAL entry at rva 0x47d560.

The .pdata entry at 0x47d5bc was a false boundary: the real function starts at
0x47d560 (`push rbp; push rbx; push rsi; lea rbp,[rsp-0xf0]; sub rsp,0x1f0`).
Scan for E8 calls and E9 jumps to 0x47d560 and report the enclosing functions.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def refs_to(data, secs, target):
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    calls, jmps = [], []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == target:
                (calls if data[i] == 0xE8 else jmps).append(insn)
    return calls, jmps


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    for rva, what in [
        (0x47D560, "tame handler real entry"),
        (0x47D460, "neighbouring function"),
    ]:
        calls, jmps = refs_to(data, secs, S.IMAGE_BASE + rva)
        print("=== %s rva=%#x  calls=%d jmps=%d" % (what, rva, len(calls), len(jmps)))
        for c in calls[:30]:
            r = S.enclosing(funcs, c)
            print("   call rva=%#x  %s" % (
                c - S.IMAGE_BASE,
                ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))
        for c in jmps[:30]:
            r = S.enclosing(funcs, c)
            print("   jmp  rva=%#x  %s" % (
                c - S.IMAGE_BASE,
                ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
