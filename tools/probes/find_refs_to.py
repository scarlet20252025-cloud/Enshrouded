r"""Find refs (call/jmp) to an arbitrary RVA target list."""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE


def main():
    targets = [0x4A5A30, 0x4A76BF, 0x9D5770]
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = IB + next(s["va"] for s in secs if s["name"] == ".text")
    for trva in targets:
        want = IB + trva
        hits = []
        for i in range(lo, hi - 5):
            if data[i] in (0xE8, 0xE9):
                rel = struct.unpack_from("<i", data, i + 1)[0]
                insn = tlo + (i - lo)
                if insn + 5 + rel == want:
                    hits.append((insn, data[i]))
        print("target rva=%#x refs=%d" % (trva, len(hits)))
        for insn, op in hits[:20]:
            r = S.enclosing(funcs, insn)
            print("   %s rva=%#x  %s" % ("call" if op == 0xE8 else "jmp ", insn - IB,
                  ("func rva=%#x size=%d" % (r[0] - IB, r[1] - r[0])) if r else "?"))
        print()


if __name__ == "__main__":
    main()
