# WolfMount — Enshrouded wolf mount mod

A mount mod for **Enshrouded 1.0**, built as a Vulkan GLOBAL layer.

> **Status: in development, honest about it.** Read [What works today](#what-works-today)
> before installing. Nothing here pretends to work.

- **License: GPL-3.0** (`LICENSE`) — required, because part of the runtime
  mechanism is ported from [M182 Admin Pannel](https://github.com/CarlosMonroy182/EML-Temporary-Fix-Enshrouded-1.0),
  which is GPL-3.0. See [`NOTICE.md`](NOTICE.md) for the file-by-file provenance.
- **No administrator rights needed.** Per-user install, per-user registry,
  uninstall deletes two files.
- **Modifies no game file.** Ever. Uninstall is complete.

---

## What this mod is trying to do

Enshrouded has no mount system. It does, however, have a glider, a grappling
hook, and a parent/child entity hierarchy — and between them, every mechanism a
mount needs already exists:

| A mount needs | Enshrouded already has |
|---|---|
| an attach point on the animal | `HookShotAnchorSubEntity` (Root slot, +1.0 m) |
| parent/child transforms | `keen::ecs::ImpactHierarchy` |
| a riding camera | `CameraId::PlayerCameraGlider` |
| a seated pose | `CameraId::PlayerCameraSitting` |
| take control / release | `HookSwingEnter` / `HookSwingDefaultExit` / `AttachedToHook` |
| combat AI for the animal | the wolf's own enemy behaviour stack |
| follow-the-player | `AdminSpawnCommand.followPlayer` |

The wolf's faction is `WildBeast` and its `Aggro.applyEnemyValue` is true — it is
already a combat unit. So the plan is not "add a mount system", it is "make an
existing wolf rideable".

**The 1.0 binary contains zero occurrences of any mount/saddle/ride symbol.**
Everything above is a composition of shipped systems.

---

## What works today

| Feature | State |
|---|---|
| Vulkan layer + ImGui overlay (F8) | **works** |
| Command console (F9) | **works** |
| Locate the world context, entity manager, live entities | **works** (verified: 1301 entities in a loaded world) |
| Discover the `Faction` component slot at runtime | **works** |
| Spawn an entity from a template GUID | implemented, **not yet verified in game** |
| Place a spawned entity at a chosen position | implemented (post-spawn transform write), **not yet verified in game** |
| Write an entity's faction (read-back verified) | implemented, **not yet verified in game** |
| Tame a wolf with the torch | **not implemented** — see below |
| Summon bound to `Y` | implemented as "spawn from the wolf template", **not yet verified in game** |
| Riding | **not implemented** — it is a local state machine only |
| Wolf fights alongside you | **not implemented** |

### Why summon does not re-target a wolf

An earlier design remembered the last wild beast the player met and tamed it.
That cannot work in an open world: the game streams entities in and out around
the player, so walking away destroys the entity and its id, and the remembered
id then refers to nothing. A production session showed exactly this —
`last wild wolf : (none seen)` while standing in a forest.

Summon therefore creates one from the wolf template (`Create` at RVA 0x97B790
takes a GUID, not a position, and needs no wolf nearby) and moves it into place
afterwards.

### Why taming is not done

The obvious approach — send the game's own `TameWildlifeEvent` — **does not work,
and we proved why before shipping it.**

A wolf template (`Enemy_Wildbeast_wolf_earlygame`, 108 components) carries **no
`Animal` and no `Wildlife` component**. The taming handler only acts on entities
that have them. So the event is accepted (`ok=1`) and the wolf is unchanged: it
keeps attacking you. That mismatch — a successful call with no effect — is
exactly the kind of thing a mod should not ship as "working".

The fix is a different mechanism: `Faction` is a plain byte in a component slot,
and the AI reads it to decide who is an enemy. Writing `PlayerAlly` (11) is what
actually changes behaviour. That is implemented and read-back-verified; it has
not yet been exercised in a live world.

---

## Install

**Requirements**: Enshrouded 1.0 (Steam, appid 1203620), Windows x64.

```
install.bat
```

That is the whole thing. It finds the game through your Steam library, copies
two files next to `enshrouded.exe`, and registers the layer **for your user
only** (`HKCU`). No elevation, no `sudo`, no service, no patched exe.

If you keep the game somewhere Steam does not know about:

```
install.bat "D:\Games\Enshrouded"
```

### Then

1. Launch Enshrouded and load a world.
2. Press **F8** for the mod menu, **F9** for the command console.

The keys are read with `GetAsyncKeyState`, which reads *global* hardware state —
**the game window must have focus** or the keypress goes to whatever has it.
Browser overlay with the game in the background and F8 will open your browser's
find bar instead.

### Uninstall

```
uninstall.bat
```

Removes the DLL, the manifest, and the registry value. No game file was touched,
so there is nothing else to undo.

---

## Loading alongside other mods

WolfMount is a **Vulkan GLOBAL implicit layer**. Several mods in this community
want to be loaded into the same process, and they cannot all be the same thing:

- **modloader-proxy** (MIT, by Entrodor) — a DLL chainloader that proxies
  `dbghelp` / `dinput8` / `dsound` / `powrprof` / `version`. It works by
  `chainloader.ini`. WolfMount is **compatible**: our `DllMain` does nothing but
  open a log file, so loading us early is safe and we do not need to be deferred.
  Point a `[Load]` entry at `wolfmount_layer.dll` and drop the registry
  registration.
- **EML / M182** — Lua-level data patching plus a native component. Different
  mechanism, no conflict with a Vulkan layer, **except** that M182 also ships a
  native part and both of us will want the same component slots. Run one at a
  time while either is in development.
- **Aldrich Modmenu** — also a Vulkan GLOBAL layer, also ImGui. **These two
  conflict.** Two implicit layers both subclassing the window procedure and both
  drawing will fight over input. Pick one.

The registry semantics are worth writing down because they are backwards from
what you would guess:

> The value **name** is the full path to the JSON manifest.
> The value **type** is `REG_DWORD`.
> The value **data** means **0 = enabled, 1 = disabled**.

---

## Building

Only needed if you want to change the mod.

```sh
git clone --recursive https://github.com/scarlet20252025-cloud/Enshrouded.git
cd Enshrouded
build.bat            # -> build\wolfmount_layer.dll
tools\run-tests.bat  # 10 suites, must all pass
```

`--recursive` matters: Dear ImGui and the Vulkan headers are submodules pinned to
exact tags (`v1.92.9b`, `v1.4.365`). If you forgot it, `git submodule update
--init --recursive` fixes it.

**Toolchain**: any clang that targets `x86_64-w64-windows-gnu`.
[llvm-mingw](https://github.com/mstorsjo/llvm-mingw) is what this was developed
against; WinLibs works too. `build.bat` finds clang on `PATH`, or takes
`WOLFMOUNT_LLVM` as an override, and probes the toolchain's thread model so both
win32-threaded and POSIX-threaded builds link.

No MSVC, no CMake, no vcpkg. `build.bat` drives `clang` directly.

One thing that surprises people: `vulkan-1.a` is **not** in the repo. It is
generated on first build from the system `vulkan-1.dll`'s own export table,
because an import library has to match the loader the game actually loads, and a
committed binary nobody can regenerate is a bad dependency to hand someone.

---

## How it works, and why it is built this way

If you are writing a mod for this game, **this is the part worth reading**, and
it is the reason this project is public rather than a private DLL.

The community's current approach is **AOB signatures** — scan for a byte pattern
in `enshrouded.exe` and hook what you find. It works, and it breaks on every
game update, because the pattern is a snapshot of compiled code.

WolfMount does not do that. The game ships a **self-describing reflection table**
for its own ECS: 12,646 type definitions, each with its name, size, field
offsets and an FNV-1a-32 hash of its qualified name. The table is data, so it
survives recompilation, and every offset we need comes out of it at runtime
instead of out of a hardcoded pattern.

This is documented in **[`docs/TECHNIQUE.md`](docs/TECHNIQUE.md)**: how the table
is located, how the hashes are computed, how the entity manager and component
slots are found from it, and the two traps that cost us the most time.

`MODLOG.md` is the lab notebook — every claim with the evidence that produced it,
including the ones that turned out to be wrong.

---

## Layout

```
src\        layer, hooks, ecs, entityops, faction, console, mod
tools\      PE analysis, reflection dumps, KFC unpacking, tests
docs\       TECHNIQUE.md — the reusable reverse-engineering knowledge
MODLOG.md   lab notebook: every fact and how it was established
NOTICE.md   third-party provenance (GPL-3.0 obligation)
third_party\ imgui 1.92.9b, Vulkan-Headers 1.4.365
```

---

## Contributing

Issues and corrections are more useful than patches right now, particularly:

- **Which component slot is `Faction`** in your world, from `status` in the F9
  console. If it disagrees with ours, that is a bug worth knowing about.
- **Whether `spawn` works** for you, and what the log says.
- Anything in `MODLOG.md` you can falsify. Several entries there are records of
  us being wrong; more of those is fine.

If you are the author of M182, EML, modloader-proxy or Aldrich and something in
[`NOTICE.md`](NOTICE.md) is attributed wrongly, say so and it gets fixed.
