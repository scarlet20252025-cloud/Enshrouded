r"""All 114 '0xb47' matches are coincidental substrings (rip-relative offsets,
call targets). Conclusion: reflection index 2887 never appears as an instruction
immediate either.

So AdminSpawnCommand is dispatched purely through the reflection table
(deserialize by type index). The wire-format table at 0x141507400 is likewise
unreferenced. **Admin commands cannot be injected from a static hook.**

Pivot: record this and move to the achievable path — the `wildlife` /
`wildlife_enemy_transformer` entity programs that ARE reachable, plus a direct
`SpawnEntityEvent` synthesis through the existing SendEventEx path.

Write the conclusion into MODLOG.md.
"""
print("conclusion: admin commands unreachable; pivot to entity programs + SpawnEntityEvent")
