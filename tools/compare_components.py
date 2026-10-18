#!/usr/bin/env python3
"""Compare one component's value across two templates, and against the wolf."""
import json

BASE = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource"

FILES = {
    "wolf_early":   "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json",
    "saber_wild":   "2ff5b857-a1d6-4a12-be3d-706bf606145b_39768775_0.json",
    "saber_tamed":  "46723568-37fb-4695-9915-abd896816af7_39768775_0.json",
    "tame_base":    "08365b0a-2205-45d7-8f02-fecabd5d32db_39768775_0.json",
}

TYPE_KEY = "$type"
VAL_KEY = "$value"


def load(fn):
    d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
    out = {}
    for c in d.get("components", []):
        out[c.get(TYPE_KEY)] = c.get(VAL_KEY)
    return d.get("name"), out


def main():
    loaded = {}
    for k, fn in FILES.items():
        n, c = load(fn)
        loaded[k] = c
        print("%-12s %-46s n=%d" % (k, n, len(c)))
    print()

    interesting = [
        "keen::ecs::Faction",
        "keen::ecs::IsTame",
        "keen::ecs::Animal",
        "keen::ecs::Wildlife",
        "keen::ecs::UnitTransformer",
        "keen::ecs::WildlifeTransformer",
        "keen::ecs::NetworkAnimal",
        "keen::ecs::NetworkWildlife",
        "keen::ecs::OwnerRelationship",
        "keen::ecs::PacifiedState",
        "keen::ecs::EnemyPhases",
        "keen::ecs::ThreatBonus",
        "keen::ecs::Intelligence",
        "keen::ecs::CombatTargetActor",
        "keen::ecs::Enemy01BehaviorState",
    ]
    keys = list(FILES.keys())
    print("%-36s %s" % ("component", "  ".join("%-11s" % k for k in keys)))
    for t in interesting:
        row = []
        for k in keys:
            row.append("%-11s" % ("YES" if t in loaded[k] else "-"))
        print("%-36s %s" % (t, "  ".join(row)))
    print()

    for t in ("keen::ecs::Faction", "keen::ecs::Animal"):
        print("=== %s ===" % t)
        for k in keys:
            v = loaded[k].get(t)
            if v is None:
                print("   %-12s <absent>" % k)
            else:
                print("   %-12s %s" % (k, json.dumps(v, ensure_ascii=False)[:220]))
        print()


if __name__ == "__main__":
    main()
