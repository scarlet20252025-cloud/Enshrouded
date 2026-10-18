r"""Find all callers of 0x1402139b0 (the SpawnEntityEvent dispatch entry)."""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

TARGET = S.IMAGE_BASE + 0x2139B0


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    calls, jmps, leas = [], [], []
    for i in range(lo, hi - 5):
        b = data[i]
        if b in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == TARGET:
                (calls if b == 0xE8 else jmps).append(insn)
        elif b == 0x48 and data[i + 1] == 0x8D and (data[i + 2] & 0xC7) == 0x05:
            rel = struct.unpack_from("<i", data, i + 3)[0]
            insn = tlo + (i - lo)
            if insn + 7 + rel == TARGET:
                leas.append(insn)
    print("calls=%d jmps=%d leas=%d" % (len(calls), len(jmps), len(leas)))
    for tag, lst in (("call", calls), ("jmp ", jmps), ("lea ", leas)):
        for a in lst[:40]:
            r = S.enclosing(funcs, a)
            print("  %s rva=%#x  %s" % (tag, a - S.IMAGE_BASE,
                  ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
