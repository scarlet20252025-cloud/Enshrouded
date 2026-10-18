"""Compare the VALUES of shared components between two templates.

The component SET is often identical (a tame hound and a wild wolf share 108
components), so what makes one a pet must be a field value. This dumps those.

Usage: python tools/tpl_vals.py TemplateA TemplateB [ComponentName ...]
       python tools/tpl_vals.py A B --all
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def find(name):
    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if str(d.get("name", "")) == name:
            return d
    return None


def comp_map(d):
    out = {}
    for c in d.get("components") or []:
        out[c.get("$type")] = c.get("$value")
    return out


def flat(v, prefix="", depth=0, out=None):
    if out is None:
        out = {}
    if depth > 6:
        return out
    if isinstance(v, dict):
        for k, sub in v.items():
            flat(sub, "%s/%s" % (prefix, k), depth + 1, out)
    elif isinstance(v, list):
        out[prefix + "/len"] = len(v)
        for i, sub in enumerate(v[:4]):
            flat(sub, "%s[%d]" % (prefix, i), depth + 1, out)
    else:
        out[prefix] = v
    return out


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    a, b = find(argv[1]), find(argv[2])
    if not a or not b:
        print("template not found")
        return 1

    ca, cb = comp_map(a), comp_map(b)
    shared = sorted(set(ca) & set(cb))

    want = argv[3:]
    all_mode = "--all" in want
    want = [w for w in want if w != "--all"]

    for comp in shared:
        if want and not any(w in comp for w in want):
            continue
        fa = flat(ca[comp], comp)
        fb = flat(cb[comp], comp)
        diffs = []
        for k in sorted(set(fa) | set(fb)):
            va, vb = fa.get(k, "<absent>"), fb.get(k, "<absent>")
            if va != vb:
                diffs.append((k, va, vb))
        if not diffs:
            continue
        if not all_mode and len(diffs) > 40 and not want:
            print("%s: %d differing fields (use a name filter)" % (comp, len(diffs)))
            continue
        print("== %s" % comp)
        for k, va, vb in diffs[:60]:
            print("   %-58s A=%-22s B=%s" % (k[:58], str(va)[:22], str(vb)[:30]))
        if len(diffs) > 60:
            print("   ... %d more" % (len(diffs) - 60))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
