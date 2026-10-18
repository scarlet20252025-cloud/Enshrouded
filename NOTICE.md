# Third-party attribution and provenance

WolfMount is licensed under **GPL-3.0** (see `LICENSE`). That is not a free
choice: parts of this mod are derived from another GPL-3.0 project, so the
copyleft applies. This file records exactly what came from where, because a
GPL obligation you cannot trace is an obligation you cannot honour.

## M182 Admin Pannel — the source of the runtime mechanism

- **Upstream**: <https://github.com/CarlosMonroy182/EML-Temporary-Fix-Enshrouded-1.0>
- **Author**: Carlos Monroy ("M182")
- **License**: GPL-3.0 (the archive ships the full GPL-3.0 text as `LICENSE`)
- **Distribution**: Nexus Mods, "M182 Admin Pannel"

M182 is itself built on **EML** by **Brabb3l** (also GPL-3.0), which is where the
native-reflection-table approach originates.

### What WolfMount took from it

| WolfMount file | Derived from | What was taken |
|---|---|---|
| `src/layout.h` | M182 `layout()` | The entity-component table layout: entity definition `+0x00` is a 640-bit occupancy bitmap, `+0x84` a `u16` offset table, `+0xa84` a `u16` stride table; slot address = `chunk + offset + stride * slot`. |
| `src/entitymgr.h` | M182 entity lookup | The entity manager's open-addressed hash map at `manager+0x148` (bitmap / capacity / keys / values / count), the record layout at `+0x10/+0x18/+0x20/+0x30`, and the bucket hash constant `0x045d9f3b`. |
| `src/faction.h` | M182 `faction.rs` | The `isEnemy(a, b)` truth table, obtained upstream by executing the game's own machine code under emulation across all 256x256 faction pairs. |
| `src/entityops.cpp` | M182 `spawn_now()`, `faction_addresses()` | The spawn descriptor shape (component array of 24-byte `{hash, ptr, size}` entries) and the "Faction is a memory byte, not a queue record" conclusion. |
| `src/gamedata.h` | M182 constants | Cross-checked component hashes (`CurrentTransform`, `OverrideLevel`, `Faction`, `IsTame`) and the fixed-point position unit (1 metre = 2^32). |

### What WolfMount did NOT take

- No M182 source code is copied verbatim; the ports are reimplementations in
  C++ against the same reverse-engineered facts, re-verified against the
  shipped 1.0 binary with our own tools (`tools/scanrefs.py`,
  `tools/dump_type.py`, `tools/tpl_guid.py`).
- M182's Rust runtime, its Lua layer, its EML wiring, its PvP/team/safe-zone
  features and its ImGui panel are not present here.
- M182's AOB signatures are not used. WolfMount resolves everything through the
  game's own self-describing reflection table plus PE-header-derived offsets,
  because byte patterns break on every game update and a table does not.

### Verification notes

Every ported fact was independently re-derived rather than trusted:

- `tools/peek.py`, `tools/scanrefs.py` — PE section table read from the headers
  (not hand-copied; an earlier hand-copied table was wrong and produced a day of
  false conclusions, see `MODLOG.md`).
- `tools/dump_type.py` — dumps any type from the game's reflection table.
- `tools/tpl_guid.py` — maps template names to the 16-byte GUIDs the entity
  factory takes; validated by round-tripping `1_Player`, whose filename UUID and
  baked GUID are byte-identical.
- `tools/classify_component.py` — proves which components have an Enqueue write
  site and which do not.

## modloader-proxy — the loader this mod is designed to sit behind

- **Upstream**: <https://github.com/Entrodor/modloader-proxy> (as shipped in
  "Modloader Proxy X64 162 1.0.0")
- **Author**: Entrodor
- **License**: MIT

Not vendored, not modified, not redistributed here. WolfMount is written so that
it can be chainloaded by it (see "Loading WolfMount" in `README.md`). The
compatibility is a design constraint, not a code dependency: we export a
`DllMain` that does nothing but open a log, so loading us early is safe.

## Aldrich Modmenu — the overlay precedent

- **Distribution**: Nexus Mods, "Aldrich Modmenu"
- **License**: none declared in the archive; treated as **reference only**

Studied for one purpose: to confirm that a **Vulkan GLOBAL implicit layer** is a
viable overlay host for this game, and how such a layer is registered. No code
taken. WolfMount's layer, its `VK_LAYER_WOLFMOUNT_wolfmount.json` manifest and
its `vkNegotiateLoaderLayerInterfaceVersion` are written from the Vulkan loader
specification.

## Game data

Component names, hashes, field offsets, template GUIDs and enum values are facts
about the shipped game, read out of `enshrouded.exe` and its KFC resource
containers. They are not copyrightable expression, but they are recorded here so
anyone can re-derive them: see `MODLOG.md` for the method behind each one.

KFC unpacking used **kfc-parser** by **Brabb3l** (part of EML).

## Libraries

| Library | Version | License | Use |
|---|---|---|---|
| Dear ImGui | 1.92.9b | MIT | overlay UI |
| Vulkan-Headers | 1.4.365 | Apache-2.0 | layer entry points |

Both are used unmodified. ImGui is built with `IM_ASSERT` redirected to a
non-aborting logger (`src/wm_imgui_assert.h`) because an assert inside a Vulkan
layer becomes a silent game crash.

## If you are one of the authors above

Open an issue or a discussion. If you believe something here is attributed
wrongly, or that code was taken that should not have been, say so and it will be
corrected or removed.
