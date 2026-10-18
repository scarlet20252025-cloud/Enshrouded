import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"

def fnv(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h

targets = {
    0xCC0D57E0: "HitEvent",
    0xD079D101: "EventA_size168",
    0xD8EC982A: "EntityDiedEvent",
    0x537B675C: "TameWildlifeEvent",
    0x06DBFCA2: "AdminSpawnCommand",
    0x14CC3955: "AdminDebugEnemyAction",
    0xAB8BF04F: "ScenePlayerCamera",
}

d = json.load(open(REFL, encoding="utf-8"))

found = {}

def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + f"[{i}]")
    else:
        yield path, o

for p, v in walk(d):
    if isinstance(v, str) and v.startswith("keen::"):
        h = fnv(v)
        if h in targets:
            found.setdefault(h, []).append((v, p))

for h, name in targets.items():
    hits = found.get(h, [])
    if hits:
        for v, p in hits[:4]:
            print(f"{name:22s} {v}   ({p})")
    else:
        print(f"{name:22s} -- no match in reflection_data.json")
    print()
