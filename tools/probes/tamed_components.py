r"""Dump the component JSON of three templates: tamed sabertooth (x2) and the
earlygame wolf. Learns the true template schema from the file layout.
"""
import io
import json
import os
import sys

ROOT = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
WANT = [
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed",
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed_Night_Patrol",
    "Enemy_Wildbeast_wolf_earlygame",
]


def find(name):
    for dp, _d, fs in os.walk(ROOT):
        for fn in fs:
            if fn.startswith(name):
                return os.path.join(dp, fn), fn
    return None, None


def main():
    for name in WANT:
        p, fn = find(name)
        if not p:
            print("NOT FOUND", name)
            continue
        t = json.load(io.open(p, "r", encoding="utf-8"))
        print("=" * 72)
        print("%s  file=%s  (%d components)" % (name, fn,
                                               len(t.get("components") or [])))
        print("top-level keys:", list(t.keys()))
        for c in t.get("components") or []:
            short = c.get("type") or c.get("$type") or "?"
            leaf = short.split(".")[-1]
            if leaf in ("Faction", "Animal", "Wildlife", "IsTame", "EnemyPhases",
                        "ThreatBonus", "UnitTransformer", "NetworkWildlife",
                        "DynamicWildlife"):
                print("   [%s] %s" % (leaf, json.dumps(c, ensure_ascii=False)[:500]))
        comps = t.get("components") or []
        if comps:
            print("   -- sample component entry --")
            print("   " + json.dumps(comps[0], ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
