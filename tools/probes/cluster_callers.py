r"""Find callers of 0x47fb73 (the function that tails into the dispatcher)."""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def refs_to(data, secs, target):
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    calls, jmps, leas = [], [], []
    for i in range(lo, hi - 5):
        b = data[i]
        if b in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == target:
                (calls if b == 0xE8 else jmps).append(insn)
        elif b == 0x48 and data[i + 1] == 0x8D and (data[i + 2] & 0xC7) == 0x05:
            rel = struct.unpack_from("<i", data, i + 3)[0]
            insn = tlo + (i - lo)
            if insn + 7 + rel == target:
                leas.append(insn)
    return calls, jmps, leas


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    for rva in [0x47FB73, 0x47FB63, 0x47FB5B, 0x480341, 0x480559, 0x4806A0]:
        c, j, l = refs_to(data, secs, S.IMAGE_BASE + rva)
        print("=== rva=%#x  calls=%d jmps=%d leas=%d" % (rva, len(c), len(j), len(l)))
        for tag, lst in (("call", c), ("jmp ", j), ("lea ", l)):
            for a in lst[:20]:
                r = S.enclosing(funcs, a)
                print("   %s rva=%#x  %s" % (
                    tag, a - S.IMAGE_BASE,
                    ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
