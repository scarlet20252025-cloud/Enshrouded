r"""Locate 0x14012CF5C0 by scanning backwards for the function start (.pdata)."""
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    t = S.IMAGE_BASE + 0x12CF5C0
    r = S.enclosing(funcs, t)
    print("enclosing: %s" % (("rva=%#x..%#x size=%d" % (
        r[0] - S.IMAGE_BASE, r[1] - S.IMAGE_BASE, r[1] - r[0])) if r else "none"))
    # print a few functions around
    idx = [k for k, (b, e) in enumerate(funcs) if b <= t < e]
    if idx:
        for k in range(idx[0] - 2, idx[0] + 4):
            if 0 <= k < len(funcs):
                b, e = funcs[k]
                print("  rva=%#x..%#x size=%d" % (b - S.IMAGE_BASE, e - S.IMAGE_BASE, e - b))


if __name__ == "__main__":
    main()
