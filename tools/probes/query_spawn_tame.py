"""Query reflection_data.json for spawn / tame / player-position related types."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFL = ROOT / "tools" / "kfc" / "reflection_data.json"

d = json.load(open(REFL, "r", encoding="utf-8"))
types = d["types"] if isinstance(d, dict) and "types" in d else d


def qn(t):
    return t.get("qualifiedName") or t.get("name") or "?"


def dump(i, depth=0, seen=None):
    seen = seen if seen is not None else set()
    if i in seen or depth > 2:
        return
    seen.add(i)
    t = types[i]
    print("%s[%d] %s  size=%s ptype=%s inner=%s" %
          ("  " * depth, i, qn(t), t.get("size"), t.get("primitiveType"), t.get("innerType")))
    sf = t.get("structFields") or {}
    ef = t.get("enumFields") or {}
    if isinstance(sf, dict):
        for name, f in sf.items():
            if isinstance(f, dict):
                print("%s   +%-4s %-28s %s" % ("  " * depth, f.get("dataOffset"),
                                               f.get("name"), f.get("type")))
    if isinstance(ef, dict):
        for name, f in ef.items():
            if isinstance(f, dict):
                print("%s   %-30s = %s" % ("  " * depth, name, f.get("value")))
    it = t.get("innerType")
    if isinstance(it, int) and it != i and depth < 1:
        dump(it, depth + 1, seen)


def find(sub, limit=40):
    out = []
    for i, t in enumerate(types):
        n = qn(t)
        if sub.lower() in n.lower():
            out.append((i, n, t.get("size")))
    return out[:limit]


print("=" * 70)
print("TameWildlifeEvent")
print("=" * 70)
for i, t in enumerate(types):
    if qn(t) == "keen::actor::TameWildlifeEvent":
        dump(i)
        break

print()
print("=" * 70)
print("types whose name contains 'Spawn'")
print("=" * 70)
for i, n, sz in find("Spawn"):
    print("  [%5d] %-58s size=%s" % (i, n, sz))

print()
print("=" * 70)
print("types whose name contains 'Tame'")
print("=" * 70)
for i, n, sz in find("Tame"):
    print("  [%5d] %-58s size=%s" % (i, n, sz))

print()
print("=" * 70)
print("PlayerFocus / ClientPlayerFocus / WorldPosition / CurrentTransform")
print("=" * 70)
for want in ["keen::ecs::PlayerFocus", "keen::ecs::ClientPlayerFocus",
             "keen::WorldPosition", "keen::ecs::CurrentTransform",
             "keen::ecs::WorldTransform", "keen::WorldTransform"]:
    for i, t in enumerate(types):
        if qn(t) == want:
            dump(i)
            break
