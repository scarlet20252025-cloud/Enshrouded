r"""Verify the tame handler's caller: who calls 0x47d5bc and with what?

0x47d5bc has a .pdata entry but starts mid-register-save, meaning it is a
tail-called / thunked continuation. Listing its callers tells us the real entry
point that decides "this is a TameWildlifeEvent".
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    want = S.IMAGE_BASE + 0x47D5BC
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    hits = []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == want:
                hits.append(insn)
    print("callers of 0x47d5bc: %d" % len(hits))
    for c in hits:
        r = S.enclosing(funcs, c)
        print("  caller rva=%#x  %s" % (
            c - S.IMAGE_BASE,
            ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))

    # Also: who references the whole 577-byte function region by address?
    # (e.g. a vtable or a jump table entry)
    print("\nabsolute u64 refs to func start:")
    for sec in secs:
        i = sec["raw"]
        hi2 = sec["raw"] + sec["rawsize"]
        pat = struct.pack("<Q", want)
        while True:
            i = data.find(pat, i, hi2)
            if i < 0:
                break
            print("  %s rva=%#x" % (sec["name"],
                                    S.IMAGE_BASE + sec["va"] + (i - sec["raw"])))
            i += 1


if __name__ == "__main__":
    main()
