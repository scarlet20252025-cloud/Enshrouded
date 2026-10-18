r"""Find who calls the dispatcher 0x47fc97 - that is the message routing layer.

The tame handler is reached only via 0x47fc97, which is itself a big if/else on
`cmpb` (faction/enum values), NOT a hash switch. So the hash->handler mapping
happens further up. Find callers of 0x47fc97.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def refs_to(data, secs, target):
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    calls, jmps, leas = [], [], []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == target:
                (calls if data[i] == 0xE8 else jmps).append(insn)
        elif data[i] == 0x48 and data[i + 1] == 0x8D:  # lea reg, [rip+d]
            rel = struct.unpack_from("<i", data, i + 3)[0]
            insn = tlo + (i - lo)
            if insn + 7 + rel == target:
                leas.append(insn)
    return calls, jmps, leas


def show(funcs, lst, tag):
    for c in lst[:40]:
        r = S.enclosing(funcs, c)
        print("   %s rva=%#x  %s" % (
            tag, c - S.IMAGE_BASE,
            ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    for rva, what in [
        (0x47FC97, "dispatcher (tame branch owner)"),
        (0x481830, "its first callee"),
        (0x47D0D0, "the cmpb-target getter"),
    ]:
        c, j, l = refs_to(data, secs, S.IMAGE_BASE + rva)
        print("=== %s rva=%#x  calls=%d jmps=%d leas=%d" % (what, rva, len(c), len(j), len(l)))
        show(funcs, c, "call")
        show(funcs, j, "jmp ")
        show(funcs, l, "lea ")


if __name__ == "__main__":
    main()
