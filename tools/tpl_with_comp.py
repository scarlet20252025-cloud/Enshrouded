"""Find which templates carry a component, printing their names."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def main(argv):
    if len(argv) < 2:
        print("usage: python tools/tpl_with_comp.py <ComponentName> [substring-filter]")
        return 2
    comp = argv[1]
    filt = argv[2].lower() if len(argv) > 2 else ""
    hits = []
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        name = str(d.get("name", ""))
        if filt and filt not in name.lower():
            continue
        for c in d.get("components") or []:
            if c.get("$type") == comp:
                hits.append(name)
                break
    hits.sort()
    for h in hits:
        print("  " + h)
    print("\n%d template(s) carry %s" % (len(hits), comp))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
