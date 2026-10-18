"""List template names (not filenames) whose name matches a substring."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def main(argv):
    if len(argv) < 2:
        print("usage: python tools/tpl_list.py <substring> [more...]")
        return 2
    needles = [a.lower() for a in argv[1:]]
    hits = []
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        name = str(d.get("name", ""))
        if any(n in name.lower() for n in needles):
            hits.append((name, len(d.get("components") or []),
                         os.path.basename(path).split("_")[0]))
    hits.sort()
    for name, n, guid in hits:
        print("%-58s %4d  %s" % (name[:58], n, guid))
    print("\n%d template(s)" % len(hits))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
