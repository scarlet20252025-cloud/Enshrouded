def fnv(s):
    h = 2166136261
    for b in s.encode():
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h
for n in ["keen::ecs::CurrentTransform","keen::ecs::PlayerFocus",
          "keen::ecs::Faction","keen::ecs::IsTame",
          "keen::ecs::ClientPlayerFocus","keen::ecs::WorldTransform"]:
    print(f"{n} -> 0x{fnv(n):08X}")
