r"""Find who calls the 16 descriptor thunks, so we learn the calling convention
and — more importantly — whether the enemy_transformer descriptor's handler
(0x140480c70) is reachable from a place we can also reach.

For each thunk rva in 0x12cf5c0..0x12cf6b0, scan .text for E8 rel32 calls.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE
THUNKS = [0x12CF5C0 + i * 0x10 for i in range(16)]


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = IB + next(s["va"] for s in secs if s["name"] == ".text")

    # pre-scan all E8/E9 with targets
    targets = {}
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            targets.setdefault(insn + 5 + rel, []).append((insn, data[i]))

    for trva in THUNKS:
        tv = IB + trva
        hits = targets.get(tv, [])
        print("thunk rva=%#x  callers=%d" % (trva, len(hits)))
        for insn, op in hits[:12]:
            r = S.enclosing(funcs, insn)
            print("    %s rva=%#x  %s" % ("call" if op == 0xE8 else "jmp",
                  insn - IB,
                  ("func rva=%#x size=%d" % (r[0] - IB, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
