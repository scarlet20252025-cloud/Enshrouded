r"""Find the .pdata function boundaries around 0x47fc97 to identify its neighbours.

The dispatcher has no direct callers, so it must be a virtual/indirect target.
Look for its address stored anywhere (e.g. a vtable slot, a registration
descriptor) or referenced via `lea` with a different encoding
(48 8d 0d/05/15/35/3d ... rel32).
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

TARGET = S.IMAGE_BASE + 0x47FC97


def main():
    data = S.load()
    secs = S.sections(data)

    # 1. Direct u64 pointer in any section.
    pat = struct.pack("<Q", TARGET)
    for sec in secs:
        i = sec["raw"]
        hi = sec["raw"] + sec["rawsize"]
        n = 0
        while True:
            i = data.find(pat, i, hi)
            if i < 0:
                break
            print("u64 ref in %s rva=%#x" % (sec["name"],
                                             S.IMAGE_BASE + sec["va"] + (i - sec["raw"])))
            i += 1
            n += 1
            if n > 20:
                break

    # 2. lea r, [rip+d] variants (48 8D /r with mod=00 rm=101)
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
    n = 0
    for i in range(lo, hi - 7):
        if data[i] == 0x48 and data[i + 1] == 0x8D:
            modrm = data[i + 2]
            if (modrm & 0xC7) == 0x05:  # [rip+disp32]
                rel = struct.unpack_from("<i", data, i + 3)[0]
                insn = tlo + (i - lo)
                if insn + 7 + rel == TARGET:
                    print("lea rva=%#x" % (insn - S.IMAGE_BASE))
                    n += 1
    print("total lea refs: %d" % n)

    # 3. Neighbouring pdata functions to understand the cluster.
    funcs = S.pdata_funcs(data, secs)
    idx = [k for k, (b, e) in enumerate(funcs) if b <= TARGET < e]
    print("\nneighbourhood:")
    if idx:
        for k in range(idx[0] - 3, idx[0] + 5):
            if 0 <= k < len(funcs):
                b, e = funcs[k]
                print("  rva=%#x..%#x size=%d" % (b - S.IMAGE_BASE, e - S.IMAGE_BASE, e - b))


if __name__ == "__main__":
    main()
