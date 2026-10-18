r"""Dump the three templates' key components with the name index resolved."""
import io
import json
import os

ROOT = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource"
IDX = r"E:\DSH\肥鱼乐园\WolfMount\tools\_name_index.json"
WANT = [
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed",
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed_Night_Patrol",
    "Enemy_Wildbeast_wolf_earlygame",
    "Enemy_Scavenger_ColdHeights_SnowSabertooth",
]
LEAF = {"Faction", "Animal", "Wildlife", "IsTame", "EnemyPhases", "ThreatBonus",
        "UnitTransformer", "NetworkWildlife", "DynamicWildlife", "TamedBy",
        "Follower", "OwnedBy"}


def main():
    idx = json.load(io.open(IDX, "r", encoding="utf-8"))
    for w in WANT:
        fn = idx.get(w)
        if not fn:
            print("NOT FOUND", w)
            continue
        d = json.load(io.open(os.path.join(ROOT, fn), "r", encoding="utf-8"))
        print("=" * 72)
        print("%s  (%d components)  parent=%s" % (w, len(d.get("components") or []),
                                                  d.get("parent") or d.get("template")))
        for c in d.get("components") or []:
            t = c.get("type") or c.get("$type") or "?"
            leaf = t.split(".")[-1]
            if leaf in LEAF:
                print("  [%s] %s" % (leaf, json.dumps(c, ensure_ascii=False)[:300]))


if __name__ == "__main__":
    main()
