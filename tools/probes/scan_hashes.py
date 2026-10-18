import json, sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

d = json.load(open(REFL, encoding="utf-8"))
types = d["types"]
by_q = {t.get("qualifiedName"): t for t in types}

# Sections (from llvm-objdump -h)
SECTIONS = [
    (".text",  0x140001000, 0x400, 0x13AE480),
    (".rdata", 0x1413B0000, 0x13AEA00, 0xC04CEE),
    (".data",  0x141FB5000, 0x1FAEA00, 0x1B200),
    (".pdata", 0x142836000, 0x14295E000 - 0x142836000, 0xD4FC4),
]

def sec_of(rva):
    for n, va, raw, sz in SECTIONS:
        if va <= rva < va + sz:
            return n
    return None

NAMES = [
    "keen::ecs::ClientPlayerInput",
    "keen::ecs::PlayerInput",
    "keen::ecs::AdminClientPlayerInputData",
    "keen::ecs::AdminSpawnCommand",
    "keen::ecs::AdminDebugEnemyAction",
    "keen::ecs::ScenePlayerCamera",
    "keen::ecs::SceneCellMessage",
    "keen::ecs::ProgramEntitiesMessage",
    "keen::ecs::GetProgramEntitiesMessage",
    "keen::ecs::EntitySpawnData",
    "keen::ecs::SpawnComponent",
    "keen::ecs::EntityDiedEvent",
    "keen::ecs::NoiseEvent",
    "keen::ecs::HitEvent",
    "keen::actor::TameWildlifeEvent",
    "keen::actor::SpawnEntityEvent",
    "keen::actor::SpawnEntityBaseEvent",
    "keen::ecs::Animal",
    "keen::ecs::IsTame",
    "keen::ecs::Faction",
    "keen::ecs::CurrentTransform",
    "keen::ecs::HookShot",
]

blob = open(EXE, "rb").read()

def find_all(needle):
    out = []
    start = 0
    while True:
        i = blob.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out

print(f"exe size = {len(blob)} (0x{len(blob):X})")
print()
for n in NAMES:
    t = by_q.get(n)
    if not t:
        print(f"{n}: NOT IN REFLECTION")
        continue
    h = t["qualifiedHash"]
    needle = struct.pack("<I", h)
    hits = find_all(needle)
    parts = []
    for off in hits:
        # map file offset -> rva
        rva = None
        for sname, va, raw, sz in SECTIONS:
            if raw <= off < raw + sz:
                rva = va + (off - raw)
                break
        if rva is None:
            parts.append(f"off 0x{off:X} [hdr?]")
        else:
            s = sec_of(rva) or "?"
            parts.append(f"{s} rva 0x{rva:X}")
    print(f"{n}")
    print(f"   qh=0x{h:08X}  hits={len(hits)}")
    for p in parts[:12]:
        print(f"      {p}")
    print()
