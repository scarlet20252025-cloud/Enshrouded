import json, sys, io, re
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

names = [
    "keen::ecs::ClientPlayerInput",
    "keen::ecs::AdminClientPlayerInputData",
    "keen::ecs::AdminSpawnCommand",
    "keen::ecs::AdminTeleportCommand",
    "keen::ecs::AdminKillFactionCommand",
    "keen::ecs::AdminDebugEnemyAction",
    "keen::ecs::ScenePlayerCamera",
    "keen::ecs::SceneCellMessage",
    "keen::ecs::ProgramEntitiesMessage",
    "keen::ecs::GetProgramEntitiesMessage",
    "keen::ecs::ProgramsMessage",
    "keen::ecs::EntityDiedEvent",
    "keen::ecs::NoiseEvent",
    "keen::ecs::HitEvent",
    "keen::actor::TameWildlifeEvent",
    "keen::ecs::IsTame",
    "keen::ecs::Animal",
    "keen::ecs::Faction",
    "keen::ecs::HookShot",
    "keen::ecs::CurrentTransform",
    "keen::ecs::EntityComponentEntry",
    "keen::WorldPosition",
    "keen::WorldTransform",
]

by_q = {}
for t in types:
    by_q[t.get("qualifiedName")] = t

for n in names:
    t = by_q.get(n)
    if not t:
        print(f"{n}: NOT FOUND")
        continue
    h = t["qualifiedHash"]
    print(f"{n}: idx={t['index']} size={t['size']} qh={h:08X}")

    # dump struct fields if present
    sf = t.get("structFields")
    if sf:
        print("   fields: " + ", ".join(
            f"{k}@{v['dataOffset']}(t{v['type']})" for k, v in sf.items()))
    else:
        for key in ("enumValues", "fields"):
            if t.get(key):
                print(f"   {key}: {t[key]}")
    print()
