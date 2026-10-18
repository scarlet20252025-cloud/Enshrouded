r"""Find which section contains RVA 0x12cf5c0."""
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def main():
    data = S.load()
    secs = S.sections(data)
    for rva in (0x12CF5C0, 0x12CF610):
        for s in secs:
            if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
                print("rva=%#x in %s (va=%#x vsize=%#x)" % (
                    rva, s["name"], s["va"], s["vsize"]))
                break
        else:
            print("rva=%#x not in any section" % rva)


if __name__ == "__main__":
    main()
