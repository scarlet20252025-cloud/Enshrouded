import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

def callers_of(target_va):
    out = []
    i = 0
    n = len(text)
    while i < n - 5:
        if text[i] == 0xE8:
            rel = struct.unpack_from("<i", text, i + 1)[0]
            if TEXT_VA + i + 5 + rel == target_va:
                out.append(TEXT_VA + i)
        i += 1
    return out

targets = {
    "PlayerInput reg thunk": 0x140281A00,
    "EnemySettings reg thunk": 0x1402819C0,
    "OverrideLevel reg thunk": 0x1402819E0,
    "CurrentTransform reg thunk": 0x14021D470,
    "SlotAttachment reg thunk": 0x14031D280,
    "EntityAttachment reg thunk": 0x14031D180,
    "ImpactHierarchy reg thunk": 0x140212F20,
    "Faction reg thunk": 0x14021D570,
    "OwnerRelationship reg thunk": 0x14024E630,
    "Actor reg thunk": None,
}

for name, va in targets.items():
    if va is None:
        continue
    cs = callers_of(va)
    print(f"{name:34s} 0x{va:X}  -> {len(cs)} callers")
    for c in cs[:40]:
        print(f"      from 0x{c:X}")
    print()
