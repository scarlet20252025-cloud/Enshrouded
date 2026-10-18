// ============================================================================
//  WolfMount — live entity operations
//
//  The runtime half of layout.h / entitymgr.h: find the entity manager, locate
//  the global Faction component slot, read and write component bytes, and spawn
//  an entity from a template GUID.
//
//  DESIGN NOTE — why there is no Create hook here
//  ----------------------------------------------
//  The community mod (M182) hooks the entity factory at RVA 0x97B790 with a
//  naked stub so it can watch what the game spawns. We do not need that: the
//  factory is an ordinary function, so calling it directly at its RVA is both
//  simpler and safer. Hooking it would mean replaying its first 19 prologue
//  bytes inside a trampoline, and those bytes write the incoming register
//  arguments into the *shadow space* relative to rsp — which a replayed
//  prologue would do 8 bytes off, because the trampoline is reached by a `call`
//  rather than by the original `call`. Whether that matters depends on whether
//  the body later reads those home slots back, which is not something worth
//  betting the game's stability on when a direct call works.
//
//  The manager pointer therefore arrives the same way all our other state does:
//  from the world context the game hands us through GetCtx / Enqueue.
//
//  FACTION SLOT DISCOVERY — why we can do it without knowing the player
//  -------------------------------------------------------------------
//  The engine identifies a component by its index in the 640-slot table, and
//  that index is global across every entity definition. So the Faction slot is
//  one index we need to find once.
//
//  We find it by its *values*, not its name. Faction is one byte wide and its
//  value is a 16-value enum. Any slot that
//      * is one byte wide,
//      * is present on live entities,
//      * only ever reads as a value in [0, 15],
//      * and reads BOTH 6 (a wolf) and 7 (the player)
//  is Faction. No other one-byte component in the game satisfies all four at
//  once, and the 6/7 pair in particular is what makes this unambiguous.
// ============================================================================

#pragma once

#include <cstdint>

namespace wolfmount::entityops {

// ---------------------------------------------------------------------------
//  Manager
// ---------------------------------------------------------------------------

// True once a pointer with a valid entity-map header has been found.
bool HasManager();

// The entity manager (the object whose +0x148 is the entity hash map).
void* Manager();

// Search the world context we captured for the manager. Safe to call every
// frame; it stops as soon as it succeeds. Returns true when a manager is known.
//
// Logged once with the candidate that worked, so a game update that reshapes
// the object is visible in the log instead of silent.
bool ResolveManager();

// ---------------------------------------------------------------------------
//  Entity table
// ---------------------------------------------------------------------------

// Number of live entities the manager currently holds.
int EntityCount();

// Copy up to `max` live entity ids into `out`. Returns the number written.
int ListEntities(uint32_t* out, int max);

// Fraction of a cheap liveness signal: how many entities were readable when the
// last full scan ran. Used by the menu to prove the manager is not stale.
int LastScanSize();

// ---------------------------------------------------------------------------
//  Faction
// ---------------------------------------------------------------------------

// Discover (or re-discover) the global Faction component slot index.
// Returns the slot index, or -1 when it could not be established.
int DiscoverFactionSlot();

// The slot index found by DiscoverFactionSlot, or -1.
int FactionSlot();

// Read an entity's current faction byte. Returns -1 when unknown.
int ReadFaction(uint32_t entityId);

// Write an entity's faction byte. Returns false when the entity is gone, the
// slot is unknown, or the write did not verify by read-back.
//
// The write is verified: after writing we read the byte back and compare. That
// is the difference between "we asked" and "it happened", which is exactly the
// mistake that made the old Enqueue-based SetFaction look successful while
// doing nothing.
bool WriteFaction(uint32_t entityId, uint8_t faction);

// The local player's entity id, found as the live entity whose faction is
// Player (7). Returns 0 when not yet known.
uint32_t PlayerEntityId();

// Read the player's world position in metres. Returns false when unavailable.
bool PlayerPosition(double* x, double* y, double* z);

// Every live entity whose faction is WildBeast (6) — i.e. wolves and the other
// big predators. Returns the number written.
int ListWildBeasts(uint32_t* out, int max);

// Log a read-only census: how many entities are live, how the discovered faction
// slot distributes across them, whether the player is visible through it, and
// how many wild beasts are present.
//
// Returns true only when the slot demonstrably reads the Player faction with no
// out-of-range values, i.e. when it is safe to write through. That is the
// difference between "we found a byte" and "we found Faction", and it is the
// check that was missing when an earlier Enqueue-based faction write looked
// successful while changing nothing.
//
// Read-only. Safe to call from the render thread.
bool LogEntitySnapshot();

// ---------------------------------------------------------------------------
//  Component helpers
// ---------------------------------------------------------------------------

// Read a component by slot index into `buf`. `stride` must match the slot's
// stride exactly, or the read is refused.
bool ReadComponent(uint32_t entityId, int slot, void* buf, uint16_t stride);

// Write a component by slot index. Verified by read-back.
bool WriteComponent(uint32_t entityId, int slot, const void* data, uint16_t stride);

// Address of a component for diagnostics; 0 when unavailable.
uintptr_t ComponentAddress(uint32_t entityId, int slot, uint16_t* strideOut);

// ---------------------------------------------------------------------------
//  Spawning
// ---------------------------------------------------------------------------

// The shipped player template GUID, as it appears in TemplateResource.
// Verified against tools/kfc/unpacked/TemplateResource: the template named
// "1_Player" carries exactly these 16 bytes.
extern const uint8_t kPlayerGuid[16];

// Parse "478381c5-585f-4264-b373-dbb1ea596eca" (with or without dashes, either
// case) into the 16 raw bytes the spawn descriptor wants.
//
// The 16 bytes are simply the UUID in printed order — verified against 1_Player,
// whose filename UUID and baked kPlayerGuid are byte-for-byte identical. Returns
// false on anything that is not exactly 32 hex digits.
bool ParseGuid(const char* text, uint8_t out[16]);

// Format those 16 bytes back into the canonical dashed form for logging.
void FormatGuid(const uint8_t guid[16], char out[37]);

// One entry of the named-template table, so `spawn` can take a readable name
// instead of a 32-digit hex string.
struct NamedTemplate {
    const char* name;
    const char* guid;
    const char* note;
};

// The table of templates verified to exist in the shipped data. Bounded and
// read-only; LookupTemplate returns null for an unknown name.
const NamedTemplate* Templates(int* count);
const NamedTemplate* LookupTemplate(const char* name);

// Spawn one entity from a template GUID.
//
// Returns the new entity id, or 0 on failure.
//
// IMPORTANT — the x/y/z arguments DO NOT position the entity. The factory
// (RVA 0x97B790) reads exactly two fields of the descriptor we pass it:
//     desc+0x04  16-byte template GUID    (movups 0x4(%r8),%xmm0 at 0x97B8A9)
//     desc+0x20  component count          (leaq 0x20(%r8),%rax at 0x97B7BB)
// It never reads desc+0x18, so the component array we attach there is ignored
// and the spawned entity's components — including its position — come entirely
// from the template. To place an entity, spawn it and then move it by writing
// its CurrentTransform slot directly; see MoveEntity() below.
//
// This calls the game's own entity factory at RVA 0x97B790 directly. It does
// not need the manager to have been resolved: the factory takes the manager as
// its first argument, so ResolveManager() must have succeeded first.
uint32_t SpawnAt(const uint8_t guid[16], double x, double y, double z,
                 uint32_t level);

// Write an entity's position in metres by overwriting its transform slot, after
// locating that slot by shape.
//
// This is the only way to place an entity: the spawn factory ignores the
// position we hand it. Two encodings exist and the found slot decides which is
// used, so a 32-byte float transform is never written as fixed-point:
//     keen::ecs::CurrentTransform  56 B  three sint64 fixed-point (1/2^32 m)
//     keen::ecs::Transform         32 B  float3 in metres
//
// Returns true only after a read-back confirms the write stuck.
bool MoveEntity(uint32_t entityId, double x, double y, double z);

// Find the transform slot for an entity and report its width through strideOut
// (56 for the fixed-point form, 32 for the float form). Public so diagnostics
// can report which encoding is in play without duplicating the search.
int FindTransformSlotEx(uint32_t entityId, uint16_t* strideOut);

// Convenience: spawn `count` wolves around the player at `distance` metres.
// Returns how many actually appeared (verified by looking up the returned ids).
int SpawnNearPlayer(const uint8_t guid[16], int count, double distance,
                    uint32_t level);

// Spawn and enrol the result in the follow set. Separate from SpawnNearPlayer so
// a spawn used as a test target does not start trailing the player by accident.
int SpawnFollower(const uint8_t guid[16], int count, double distance,
                  uint32_t level);

// ---------------------------------------------------------------------------
//  Following
//
//  This engine has no follow behaviour to switch on. `EnemyFeatureMask` is a
//  32-bit mask over `EnemyFeature`, whose complete enum is 27 values and has no
//  `Follow` member, so a companion cannot be told to trail the player by writing
//  a behaviour flag. `OwnerRelationship` looks like the missing link but is
//  carried by none of the 12267 shipped templates (it is attached at runtime)
//  and has no `Enqueue` write site, so it cannot be set through the component
//  path either.
//
//  So following is done from outside: remember the companion ids, and each tick
//  move them toward a point behind the player. `FollowTick` is that loop. It is
//  deliberately cheap -- the transform slot is cached per entity definition
//  (see the cache in entityops.cpp), so a tick costs a position read plus one
//  write per companion, not a 640-slot search.
// ---------------------------------------------------------------------------

// Add an entity to the follow set. Returns false when the set is full.
bool FollowAdd(uint32_t entityId);

// Drop an entity from the follow set (also happens automatically when it dies).
void FollowRemove(uint32_t entityId);

// Forget every follower.
void FollowClear();

// How many entities are currently in the follow set.
int FollowCount();

// Advance the follow loop by one tick. Call this from the render thread once per
// frame; it self-throttles, so a per-frame call is safe.
//
// Returns how many followers were moved this tick.
//
// `behindMetres` is how far behind the player a follower aims for, and
// `teleportBeyond` is the distance past which a follower is moved
// instantaneously instead of walked -- without that, a companion left behind on
// the far side of the map would spend the rest of the session catching up, or
// never survive the trip.
int FollowTick(double behindMetres, double teleportBeyond);

// ---------------------------------------------------------------------------
//  Diagnostics
// ---------------------------------------------------------------------------

// Dump one entity's component slots to the log (index, stride, first bytes).
// Bounded: only the first `maxSlots` slots, and only the first few calls.
void DumpEntity(uint32_t entityId, int maxSlots);

// One-shot answer to "why can't the player's position be read". Logs every
// entity that currently reads Faction == Player, and for each 56-byte component
// on them the raw int64 triple plus its conversion to metres. Bounded to a few
// entities and a few slots so it is safe to call from the console.
void DumpPlayerPosition();

} // namespace wolfmount::entityops
