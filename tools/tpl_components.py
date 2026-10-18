"""List the component types a template carries, and flag transform/position ones.

Usage: python tools/tpl_components.py <template-name-or-guid-prefix>
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")

KEYS = ("Transform", "Position", "Camera", "Placement", "Spatial")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    want = argv[1].lower()

    files = []
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        base = os.path.basename(path)
        if want in base.lower():
            files.append(path)
    if not files:
        # Fall back to matching the "name" field inside each template.
        for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
            try:
                d = json.load(open(path, encoding="utf-8"))
            except Exception:
                continue
            if want in str(d.get("name", "")).lower():
                files.append(path)

    if not files:
        print("no template matched %r" % want)
        return 1

    for path in files[:4]:
        d = json.load(open(path, encoding="utf-8"))
        comps = d.get("components") or []
        print("=" * 70)
        print("file    : %s" % os.path.basename(path))
        print("name    : %s" % d.get("name"))
        print("family  : %s" % d.get("family"))
        print("comps   : %d" % len(comps))
        print("-" * 70)
        for i, c in enumerate(comps):
            t = c.get("$type", "?")
            mark = " <<<" if any(k in t for k in KEYS) else ""
            print("%3d %s%s" % (i, t, mark))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
