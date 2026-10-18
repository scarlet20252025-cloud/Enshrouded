import json, struct
def fnv(s):
    h = 2166136261
    for b in s.encode():
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h
names = ["keen::actor::SpawnEntityEvent","keen::actor::SpawnEntityBaseEvent",
         "keen::ecs::AdminSpawnCommand","keen::actor::SpawnEntityCommomEvent"]
for n in names:
    print(f"{n} -> 0x{fnv(n):08X}")
