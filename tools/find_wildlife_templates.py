#!/usr/bin/env python3
"""Which templates actually carry the wildlife/tameable component set?

Answers: can a wolf ever be tamed by the game's own pipeline, and which
templates would we need to clone to get a tameable canine?
"""
import json
import os

BASE = (r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"
        r"\TemplateResource")

MARKERS = [
    "keen::ecs::Animal",
    "keen::ecs::Wildlife",
    "keen::ecs::UnitTransformer",
    "keen::ecs::IsTame",
    "keen::ecs::TamingSetup",
]


def main():
    rows = []
    files = [f for f in os.listdir(BASE) if f.endswith(".json")]
    for fn in files:
        try:
            d = json.load(open(os.path.join(BASE, fn), encoding="utf-8"))
        except Exception:
            continue
        name = d.get("name") or ""
        types = {c.get("$type") for c in d.get("components", [])}
        if "keen::ecs::Animal" in types or "keen::ecs::Wildlife" in types:
            rows.append((name, types))
    print("templates with Animal or Wildlife: %d" % len(rows))
    for n, t in sorted(rows):
        marks = " ".join(m.split("::")[-1] for m in MARKERS if m in t)
        print("   %-58s %s" % (n, marks))


if __name__ == "__main__":
    main()
