r"""Search all unpacked TemplateResource JSONs for TAMED wildbeast variants.

The game ships `Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed` — a
SCAVENGER-faction version of a wildbeast. If a wolf equivalent exists, the
game itself knows how to spawn a friendly wolf, and we only need to make it
pick that template.
"""
import io
import json
import os
import re

ROOT = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked"


def main():
    hits = []
    n = 0
    for dirpath, _dirs, files in os.walk(ROOT):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            p = os.path.join(dirpath, fn)
            n += 1
            try:
                t = json.load(io.open(p, "r", encoding="utf-8"))
            except Exception:
                continue
            name = t.get("name") or ""
            comps = t.get("components") or []
            fac = None
            has_animal = has_wildlife = has_istame = False
            for c in comps:
                cn = c.get("type") or c.get("typeQualifiedName") or ""
                if cn.endswith("::Faction"):
                    fac = c.get("faction") or c.get("value")
                if cn.endswith("::Animal"):
                    has_animal = True
                if cn.endswith("::Wildlife"):
                    has_wildlife = True
                if cn.endswith("::IsTame"):
                    has_istame = True
            low = name.lower()
            if ("wolf" in low or "wildbeast" in low or "tamed" in low) and (
                    "tame" in low or "tamed" in low or fac is not None):
                hits.append((name, fac, has_animal, has_wildlife, has_istame))
    print("scanned %d templates" % n)
    print("matches: %d" % len(hits))
    for h in sorted(hits):
        print("  %-62s fac=%-4s animal=%d wildlife=%d istame=%d" % h)


if __name__ == "__main__":
    main()
