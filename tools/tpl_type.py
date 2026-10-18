"""Show a reflection type by index, one level of fields, plus its kind.

Usage: python tools/tpl_type.py 28 206 208
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")


def main(argv):
    blob = json.load(open(DATA, "r", encoding="utf-8"))
    types = blob.get("types") or blob.get("typeDefinitions")
    for raw in argv[1:]:
        i = int(raw, 0)
        if i < 0 or i >= len(types):
            print("idx %d out of range" % i)
            continue
        t = types[i]
        print("=" * 70)
        print("idx      : %d" % i)
        for k in ("qualifiedName", "name", "size", "align", "primitiveType",
                  "kind", "type"):
            if k in t:
                print("%-10s: %s" % (k, t[k]))
        print("-" * 70)
        print(json.dumps(t, ensure_ascii=False, indent=2)[:1500])
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
