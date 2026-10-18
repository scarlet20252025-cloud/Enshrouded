r"""Verify the FNV-1a-32 hash of 'keen::actor::TameWildlifeEvent' == 0x537B675C.
The reflection record has a 'nameHash' / 'qualifiedHash' field - use it to
confirm which name the hash 0x537B675C corresponds to, so we know which of the
two TameWildlifeEvent records the submit path at 0x47d718 compares against.
"""
import io
import json

PATH = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    d = json.load(io.open(PATH, "r", encoding="utf-8"))
    types = d["types"]
    for idx in (1900, 8139):
        t = types[idx]
        qn = t["qualifiedName"]
        print("idx %d  %s" % (idx, qn))
        print("   nameHash       %#x" % t.get("nameHash", 0))
        print("   qualifiedHash  %#x" % t.get("qualifiedHash", 0))
        print("   internalHash   %#x" % t.get("internalHash", 0))
        print("   fnv1a(qn)      %#x" % fnv1a(qn))
        print("   fnv1a(name)    %#x" % fnv1a(t["name"]))
        print()
    print("target hash 0x537b675c")


if __name__ == "__main__":
    main()
