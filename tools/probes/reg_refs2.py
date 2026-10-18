r"""Widen the search: find ALL qword refs into the string arena 0x141e2b400-0x141e2bc00.

If no code references the record, the table is probably indexed by an offset
from a base pointer that is itself referenced. Find refs to the table START
(0x141e2b400) and to any 0x100-aligned address in the table.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")

    # lea rip targets in the table range
    hits = {}
    for i in range(lo, hi - 7):
        if data[i] == 0x48 and data[i + 1] == 0x8D and (data[i + 2] & 0xC7) == 0x05:
            rel = struct.unpack_from("<i", data, i + 3)[0]
            insn = tlo + (i - lo)
            tgt = insn + 7 + rel
            if 0x141E2B000 <= tgt < 0x141E2C000:
                hits.setdefault(tgt, []).append(insn)
    for tgt in sorted(hits):
        for insn in hits[tgt][:5]:
            r = S.enclosing(funcs, insn)
            print("lea rva=%#x -> %#x   %s" % (
                insn - S.IMAGE_BASE, tgt - S.IMAGE_BASE,
                ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))
    if not hits:
        print("no lea into table range")

    # u64 refs
    print("\nu64 refs:")
    n = 0
    for sec in secs:
        i = sec["raw"]
        hi2 = sec["raw"] + sec["rawsize"]
        while i + 8 <= hi2:
            v = struct.unpack_from("<Q", data, i)[0]
            if 0x141E2B000 <= v < 0x141E2C000:
                print("  %s rva=%#x -> %#x" % (sec["name"],
                                               S.IMAGE_BASE + sec["va"] + (i - sec["raw"]),
                                               v - S.IMAGE_BASE))
                n += 1
                if n > 60:
                    break
            i += 8


if __name__ == "__main__":
    main()
