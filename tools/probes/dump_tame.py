r"""Dump both TameWildlifeEvent records to settle which namespace the FNV hash
0x537B675C belongs to, and get the field offsets.
"""
import io
import json

PATH = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def main():
    d = json.load(io.open(PATH, "r", encoding="utf-8"))
    types = d["types"]
    for t in types:
        if t.get("name") == "TameWildlifeEvent":
            print("=" * 70)
            for k in ("index", "name", "namespace", "qualifiedName", "size",
                      "alignment", "parentIndex", "baseType"):
                if k in t:
                    print("%-14s %s" % (k, t[k]))
            sf = t.get("structFields")
            if sf:
                print("fields:")
                for name, meta in sf.items():
                    if isinstance(meta, dict):
                        print("   +%s %-34s %s" % (meta.get("offset"),
                                                   name,
                                                   meta.get("typeName",
                                                            meta.get("type"))))
                    else:
                        print("   ?", name, meta)
    print()
    # also print full key list of one record so we know what's available
    for t in types:
        if t.get("name") == "TameWildlifeEvent":
            print("record keys:", sorted(t.keys()))
            break


if __name__ == "__main__":
    main()
