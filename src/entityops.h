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

// Spawn one entity from a template GUID at a world position (metres).
//
// Returns the new entity id, or 0 on failure. The spawn carries a
// CurrentTransform and an OverrideLevel, which is the minimum the community mod
// found to be sufficient for an enemy template.
//
// This calls the game's own entity factory at RVA 0x97B790 directly. It does
// not need the manager to have been resolved: the factory takes the manager as
// its first argument, so ResolveManager() must have succeeded first.
uint32_t SpawnAt(const uint8_t guid[16], double x, double y, double z,
                 uint32_t level);

// Convenience: spawn `count` wolves around the player at `distance` metres.
// Returns how many actually appeared (verified by looking up the returned ids).
int SpawnNearPlayer(const uint8_t guid[16], int count, double distance,
                    uint32_t level);

// ---------------------------------------------------------------------------
//  Diagnostics
// ---------------------------------------------------------------------------

// Dump one entity's component slots to the log (index, stride, first bytes).
// Bounded: only the first `maxSlots` slots, and only the first few calls.
void DumpEntity(uint32_t entityId, int maxSlots);

} // namespace wolfmount::entityops
