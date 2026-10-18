r"""Print every component name of the wolf and the tamed sabertooth, so we can
see what the 'Tamed' suffix actually adds (no Faction/Animal leaf matched).
"""
import io
import json
import os

ROOT = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource"
IDX = r"E:\DSH\肥鱼乐园\WolfMount\tools\_name_index.json"
WANT = [
    "Enemy_Wildbeast_wolf_earlygame",
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed",
]


def main():
    idx = json.load(io.open(IDX, "r", encoding="utf-8"))
    sets = {}
    for w in WANT:
        fn = idx[w]
        d = json.load(io.open(os.path.join(ROOT, fn), "r", encoding="utf-8"))
        names = []
        for c in d.get("components") or []:
            names.append(c.get("type") or c.get("$type") or "?")
        sets[w] = names
        print("=" * 72)
        print("%s : %d" % (w, len(names)))
        for n in names:
            print("   ", n)
    a = set(sets[WANT[0]])
    b = set(sets[WANT[1]])
    print()
    print("in tamed sabertooth but not in wolf:")
    for n in sorted(b - a):
        print("   ", n)


if __name__ == "__main__":
    main()
