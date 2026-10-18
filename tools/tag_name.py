"""Resolve EntityTag GUIDs to their names by scanning the unpacked resources."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNPACKED = os.path.join(ROOT, "tools", "kfc", "unpacked")


def main(argv):
    if len(argv) < 2:
        print("usage: python tools/tag_name.py <guid-prefix> [...]")
        return 2
    needles = [a.lower().replace("-", "")[:32] for a in argv[1:]]
    found = {}
    dirs = [d for d in os.listdir(UNPACKED)
            if os.path.isdir(os.path.join(UNPACKED, d))]
    for sub in dirs:
        for path in glob.glob(os.path.join(UNPACKED, sub, "*.json")):
            base = os.path.basename(path).split("_")[0].replace("-", "").lower()
            if not any(base.startswith(n[:8]) and n[:8] == base[:8] for n in needles):
                continue
            try:
                d = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            found[base] = (sub, str(d.get("name", "")))
    for n in needles:
        hit = [(k, v) for k, v in found.items() if k.startswith(n[:8])]
        if hit:
            for k, (sub, name) in hit:
                print("%s -> [%s] %s" % (k, sub, name))
        else:
            print("%s -> not found" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
