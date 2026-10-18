"""Resolve any GUID to the resource that declares it (by $guid field)."""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNPACKED = os.path.join(ROOT, "tools", "kfc", "unpacked")


def main(argv):
    if len(argv) < 2:
        print("usage: python tools/guid_lookup.py <guid> [...]")
        return 2
    want = set()
    for a in argv[1:]:
        want.add(a.lower().replace("-", ""))
    hits = {w: [] for w in want}
    for sub in os.listdir(UNPACKED):
        d = os.path.join(UNPACKED, sub)
        if not os.path.isdir(d):
            continue
        for path in glob.glob(os.path.join(d, "*.json")):
            base = os.path.basename(path).split("_")[0].replace("-", "").lower()
            if base in want:
                try:
                    j = json.load(open(path, encoding="utf-8"))
                except Exception:
                    j = {}
                hits[base].append((sub, str(j.get("name", "")), str(j.get("$type", ""))))
    for w in sorted(want):
        if hits[w]:
            for sub, name, ty in hits[w]:
                print("%s -> [%s] name=%r type=%s" % (w, sub, name, ty))
        else:
            print("%s -> no resource declares it (probably a shared tag label)" % w)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
