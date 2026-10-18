"""Print one field (by dotted/slashed path) of a template, resolved."""
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
    return {c.get("$type"): c.get("$value") for c in (d.get("components") or [])}


def main(argv):
    if len(argv) < 3:
        print("usage: python tools/tpl_field.py <Template> <Component> [field...]")
        return 2
    d = find(argv[1])
    if not d:
        print("template not found: %s" % argv[1])
        return 1
    cm = comp_map(d)
    key = None
    for k in cm:
        if k and argv[2] in k:
            key = k
            break
    if key is None:
        print("%s has no component matching %r" % (argv[1], argv[2]))
        return 1
    v = cm[key]
    for sub in argv[3:]:
        if isinstance(v, dict) and sub in v:
            v = v[sub]
        else:
            print("  no field %r under %s" % (sub, key))
            return 1
    print("%s / %s%s" % (argv[1], key, ("/" + "/".join(argv[3:])) if len(argv) > 3 else ""))
    print(json.dumps(v, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
