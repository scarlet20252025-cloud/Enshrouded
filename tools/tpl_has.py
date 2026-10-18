"""Which templates carry a given component type?

Usage: python tools/tpl_has.py "keen::ecs::ScenePlayerCamera"
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    want = argv[1]

    hits = []
    total = 0
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        total += 1
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        for c in d.get("components") or []:
            if c.get("$type") == want:
                hits.append((d.get("name"), os.path.basename(path)))
                break

    print("scanned %d templates; %d carry %s" % (total, len(hits), want))
    for name, fn in hits[:40]:
        print("  %-50s %s" % (name, fn))
    if len(hits) > 40:
        print("  ... %d more" % (len(hits) - 40))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
