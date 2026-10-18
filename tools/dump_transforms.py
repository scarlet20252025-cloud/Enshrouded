"""Dump every reflection type whose name looks like a transform/position holder.

The player's position has to live in SOME component; we only assumed it was
`CurrentTransform` because that is the name M182's Rust layer reads. If the
player entity simply does not carry that component, or carries it unwritten,
the search has to widen to every plausible candidate.

Usage: python tools/dump_transforms.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")

KEYWORDS = ("transform", "position", "location", "placement", "spatial",
            "coordinate", "worldpos", "camera")


def main():
    blob = json.load(open(DATA, "r", encoding="utf-8"))
    types = blob.get("types") or blob.get("typeDefinitions")
    if not types:
        raise SystemExit("no types array in %s" % DATA)
    print("total types: %d" % len(types))

    hits = []
    for i, t in enumerate(types):
        name = t.get("qualifiedName") or t.get("name") or ""
        low = name.lower()
        if not any(k in low for k in KEYWORDS):
            continue
        hits.append((i, name, t))

    print("candidates: %d\n" % len(hits))
    for i, name, t in hits:
        size = t.get("size")
        align = t.get("align")
        fields = t.get("structFields") or {}
        print("%-58s idx=%-5d size=%-4s align=%s fields=%d"
              % (name, i, size, align, len(fields)))
        for fname, f in fields.items():
            off = f.get("dataOffset", f.get("offset"))
            print("      +0x%-4s %-34s %s"
                  % (("%X" % off) if isinstance(off, int) else off,
                     fname,
                     f.get("typeName") or f.get("type") or f.get("name") or "?"))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
