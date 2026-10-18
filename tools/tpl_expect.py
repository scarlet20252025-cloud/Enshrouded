"""Expected component widths for a template, derived from reflection + the
template's component list.

This is the static half of the runtime check: given what the template declares,
which stride should CurrentTransform and Transform have on a live instance of
it? If the runtime finds a different width, something is wrong.

Usage: python tools/tpl_expect.py "Enemy_Wildbeast_wolf_earlygame"
"""
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")
DATA = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")

INTERESTING = (
    "keen::ecs::CurrentTransform",
    "keen::ecs::Transform",
    "keen::ecs::LastTransform",
    "keen::ecs::RenderTransform",
    "keen::ecs::Faction",
    "keen::ecs::IsTame",
    "keen::ecs::Animal",
    "keen::ecs::Wildlife",
    "keen::ecs::UnitTransformer",
    "keen::ecs::Health",
)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    want = argv[1].lower()

    blob = json.load(open(DATA, encoding="utf-8"))
    types = blob["types"]
    size_of = {}
    idx_of = {}
    for i, t in enumerate(types):
        q = t.get("qualifiedName", "")
        idx_of[q] = i
        size_of[q] = t.get("size")

    for path in glob.glob(os.path.join(TPL_DIR, "*.json")):
        base = os.path.basename(path).lower()
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if want not in base and want not in str(d.get("name", "")).lower():
            continue

        print("=" * 66)
        print("template: %s" % d.get("name"))
        print("file    : %s" % os.path.basename(path))
        print("comps   : %d" % len(d.get("components") or []))
        print("-" * 66)
        present = {c.get("$type") for c in d.get("components") or []}
        for nm in INTERESTING:
            mark = "yes" if nm in present else " - "
            print("  [%s] %-34s size=%-5s idx=%s"
                  % (mark, nm, size_of.get(nm), idx_of.get(nm)))
        print()
        break
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
