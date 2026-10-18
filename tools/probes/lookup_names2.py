import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
d = json.load(open(REFL, encoding="utf-8"))
types = d["types"]

def fnv(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

WANT = {
    "keen::ecs::ClientPlayerInput": "9521",
}
names = [
    "keen::ecs::ClientPlayerInput",
    "keen::ecs::PlayerInput",
    "keen::ecs::ScenePlayerInput",
    "keen::ecs::ClientPlayerInputMessage",
]
for n in names:
    for t in types:
        if t.get("qualifiedName") == n:
            print(f"{n}: idx={t['index']} size={t['size']} qh={t['qualifiedHash']:08X}")
            sf = t.get("structFields") or {}
            for k, v in sf.items():
                print(f"   +{v['dataOffset']:<5} {k:<28} type={v['type']}")
            print()
            break

# Also: find every type whose name contains 'Spawn' and 'Entity'
print("=== types whose name mentions Spawn ===")
for t in types:
    nm = t.get("qualifiedName", "")
    if "Spawn" in nm:
        print(f"  idx={t['index']:<6} size={t['size']:<6} {nm}")
print()
print("=== types whose name mentions Roaming / Wildlife / Tame ===")
for t in types:
    nm = t.get("qualifiedName", "")
    if any(k in nm for k in ("Roaming", "Wildlife", "Tame", "Mount", "Ride", "Saddle", "Dismount")):
        print(f"  idx={t['index']:<6} size={t['size']:<6} {nm}")
