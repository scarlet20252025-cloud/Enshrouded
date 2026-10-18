"""Compare the component sets of named templates.

Answers the question "what does a working combat pet have that a wolf does
not, and vice versa" without hand-copying component lists.

Usage: python tools/tpl_diff.py TemplateA TemplateB
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def load_named():
    out = {}
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        name = str(d.get("name", ""))
        if not name:
            continue
        out[name] = {
            "file": os.path.basename(path),
            "comps": set(c.get("$type") for c in (d.get("components") or [])),
        }
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    a_name, b_name = argv[1], argv[2]
    db = load_named()

    missing = [n for n in (a_name, b_name) if n not in db]
    if missing:
        for n in missing:
            print("template not found: %s" % n)
        return 1

    a, b = db[a_name], db[b_name]
    print("A: %s  (%d components)" % (a_name, len(a["comps"])))
    print("B: %s  (%d components)" % (b_name, len(b["comps"])))
    print()

    only_a = sorted(a["comps"] - b["comps"])
    print("only in A (%d)" % len(only_a))
    for x in only_a:
        print("   + %s" % x)
    print()

    only_b = sorted(b["comps"] - a["comps"])
    print("only in B (%d)" % len(only_b))
    for x in only_b:
        print("   - %s" % x)
    print()

    print("shared: %d" % len(a["comps"] & b["comps"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
