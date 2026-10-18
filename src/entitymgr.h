// ============================================================================
//  WolfMount — entity manager (the world-side component table)
//
//  layout.h answers "where does slot N of this entity live". This answers
//  "which record does entity id X belong to, and what are its def/chunk/slot".
//
//  Ported from "M182 Admin Pannel" (GPL-3.0) and re-verified against our own
//  image. The storage is an open-addressed hash map:
//
//      manager + 0x148        0x58-byte map header
//          +0x08  u64* bitmap   occupancy bits, one per bucket
//          +0x10  u64  capacity power of two
//          +0x28  u32* keys     bucket -> entity id
//          +0x40  u64* values   bucket -> entity record
//          +0x54  u32  count
//
//      entity record (0x38 bytes read)
//          +0x10  u32   entity id (echo, so a stale record can be rejected)
//          +0x18  void* def      the entity definition holding the slot tables
//          +0x20  void* chunk    the component storage base
//          +0x30  u32   slot     which instance inside the chunk
//
//  The bucket hash is the engine's own, not std::hash. A different constant and
//  every lookup silently misses, so BucketOf is a verbatim transcription.
// ============================================================================

#pragma once

#include "layout.h"

#include <windows.h>

#include <cstdint>

namespace wolfmount::mgr {

// The bucket hash the engine uses.
inline uint32_t BucketOf(uint32_t id, uint64_t capacity) {
    uint32_t a = (id >> 16) ^ id;
    a = a * 0x045d9f3bu;
    uint32_t b = (a >> 16) ^ a;
    b = b * 0x045d9f3bu;
    const uint64_t h = (static_cast<uint64_t>(b) >> 16) ^ b;
    return static_cast<uint32_t>(h & (capacity - 1));
}

struct EntityRef {
    uintptr_t def   = 0;   // entity definition object (holds the slot tables)
    uintptr_t chunk = 0;   // component storage base
    uint32_t  slot  = 0;   // instance index inside the chunk
    uint32_t  id    = 0;
};

// A live map header, validated once and then reusable for many lookups.
struct MapHeader {
    uintptr_t bitmap   = 0;
    uintptr_t keys     = 0;
    uintptr_t values   = 0;
    uint64_t  capacity = 0;
    uint32_t  count    = 0;

    bool valid() const {
        return bitmap && keys && values && capacity && count;
    }
};

// Read and validate the map header at manager+0x148. Returns false when the
// pointer is not an entity manager: a power-of-two capacity with a non-zero
// count is the only shape we accept, because guessing wrong would turn into
// writes at nonsense addresses.
inline bool ReadHeader(uintptr_t manager, MapHeader* out) {
    if (!manager || !out) return false;
    uint8_t head[0x58];
    if (!layout::Read(manager + 0x148, head, sizeof(head))) return false;

    out->capacity = layout::Load64(head + 0x10);
    out->count    = layout::Load32(head + 0x54);
    out->bitmap   = static_cast<uintptr_t>(layout::Load64(head + 0x08));
    out->keys     = static_cast<uintptr_t>(layout::Load64(head + 0x28));
    out->values   = static_cast<uintptr_t>(layout::Load64(head + 0x40));

    if (!out->valid()) return false;
    if (out->capacity > (1ull << 26)) return false;
    if (out->capacity & (out->capacity - 1)) return false;
    return true;
}

// How many buckets a single lookup may probe before giving up. The map is never
// more than ~50% loaded, so a handful of probes is normal; the cap only stops a
// corrupt header from spinning.
constexpr uint32_t kMaxProbeBuckets = 4096;

// Resolve an entity id to its live record. Returns false for a dead or unknown
// entity, or when the manager pointer is wrong.
inline bool Find(uintptr_t manager, uint32_t id, EntityRef* out) {
    if (!manager || id == 0 || !out) return false;

    MapHeader h;
    if (!ReadHeader(manager, &h)) return false;

    uint32_t bucket = BucketOf(id, h.capacity);
    const uint32_t limit = h.capacity < kMaxProbeBuckets
                               ? static_cast<uint32_t>(h.capacity)
                               : kMaxProbeBuckets;
    for (uint32_t i = 0; i < limit; ++i) {
        uint8_t word[8];
        if (!layout::Read(h.bitmap + (static_cast<uint64_t>(bucket) >> 6) * 8,
                          word, sizeof(word))) {
            return false;
        }
        const uint64_t bits = layout::Load64(word);
        if (((bits >> (bucket & 63)) & 1) == 0) return false;   // empty bucket

        uint32_t key = 0;
        if (!layout::Read(h.keys + static_cast<uint64_t>(bucket) * 4, &key, 4)) {
            return false;
        }
        if (key == id) {
            uint64_t record = 0;
            if (!layout::Read(h.values + static_cast<uint64_t>(bucket) * 8,
                              &record, 8)) {
                return false;
            }
            if (record == 0) return false;

            uint8_t rec[0x38];
            if (!layout::Read(static_cast<uintptr_t>(record), rec, sizeof(rec))) {
                return false;
            }
            // Stale-record guard: the record echoes its own id.
            if (layout::Load32(rec + 0x10) != id) return false;

            out->def   = static_cast<uintptr_t>(layout::Load64(rec + 0x18));
            out->chunk = static_cast<uintptr_t>(layout::Load64(rec + 0x20));
            out->slot  = layout::Load32(rec + 0x30);
            out->id    = id;
            return out->def >= 0x10000 && out->chunk >= 0x10000;
        }
        bucket = (bucket + 1 < h.capacity) ? bucket + 1 : 0;
    }
    return false;
}

// Collect every live entity id. `out` may be null to just count.
//
// This is what replaces the old ResolveEntity/ScanEntities pair: it walks the
// real occupancy bitmap instead of assuming a dense array, so it neither reads
// past the table nor misses high ids.
inline int EnumerateIds(uintptr_t manager, uint32_t* out, int max) {
    MapHeader h;
    if (!ReadHeader(manager, &h)) return 0;

    const uint64_t words = (h.capacity + 63) / 64;
    int n = 0;
    for (uint64_t w = 0; w < words; ++w) {
        uint8_t word[8];
        if (!layout::Read(h.bitmap + w * 8, word, sizeof(word))) break;
        uint64_t bits = layout::Load64(word);
        while (bits) {
            const int bit = __builtin_ctzll(bits);
            bits &= bits - 1;
            const uint64_t bucket = w * 64 + static_cast<uint64_t>(bit);
            if (bucket >= h.capacity) break;

            uint32_t key = 0;
            if (!layout::Read(h.keys + bucket * 4, &key, 4)) continue;
            if (key == 0) continue;
            if (out && n < max) out[n] = key;
            ++n;
            if (out && n >= max) return n;
        }
    }
    return n;
}

// Is this the authority-side manager (the one that actually simulates) rather
// than the local replay copy? Only the server-side instance owns the bytes an
// AI reads, so a write to the other copy is invisible.
inline bool IsServerManager(uintptr_t manager) {
    uint8_t b = 0;
    if (!layout::Read(manager + 8, &b, 1)) return false;
    return b == 0;
}

// ---------------------------------------------------------------------------
//  Locating a component slot without knowing its name
//
//  The engine identifies a component at runtime by its position in the 640-slot
//  table, and that position is global: Faction has ONE index in every entity
//  definition that carries it. So we only have to discover the index once.
//
//  Faction is the easiest component in the game to identify, because we know its
//  value: the local player's faction byte is 7 (Player), it is one byte wide, and
//  it is present on both the player and any animal.
// ---------------------------------------------------------------------------

constexpr uint8_t kFactionPlayer = 7;
constexpr uint8_t kFactionServerMax = 15;   // FactionType is a 16-value enum

// Slot indices whose component is exactly one byte wide.
inline int ByteSlots(const uint8_t* def, int* out, int max) {
    int n = 0;
    for (int i = 0; i < layout::kComponentSlots; ++i) {
        uint16_t stride = 0;
        if (!layout::HasSlot(def, i)) continue;
        stride = layout::Load16(def + 0xa84 + i * 2);
        if (stride != 1) continue;
        if (out && n < max) out[n] = i;
        ++n;
    }
    return n;
}

// Read one component's bytes for an entity. Returns false when the slot is
// absent or the memory is not readable right now.
inline bool ReadSlot(const EntityRef& e, int index, void* buf, uint16_t stride) {
    uintptr_t addr = 0;
    uint16_t got = 0;
    if (!layout::SlotAddress(reinterpret_cast<const uint8_t*>(e.def), e.chunk,
                             e.slot, index, &addr, &got)) {
        return false;
    }
    if (stride && got != stride) return false;
    return layout::Read(addr, buf, got);
}

inline bool WriteSlot(const EntityRef& e, int index, const void* data,
                      uint16_t len) {
    uintptr_t addr = 0;
    uint16_t stride = 0;
    if (!layout::SlotAddress(reinterpret_cast<const uint8_t*>(e.def), e.chunk,
                             e.slot, index, &addr, &stride)) {
        return false;
    }
    if (stride != len) return false;
    return layout::Write(addr, data, len);
}

// Address of a component slot, or 0 when absent.
inline uintptr_t SlotAddressOf(const EntityRef& e, int index,
                               uint16_t* strideOut = nullptr) {
    uintptr_t addr = 0;
    uint16_t stride = 0;
    if (!layout::SlotAddress(reinterpret_cast<const uint8_t*>(e.def), e.chunk,
                             e.slot, index, &addr, &stride)) {
        return 0;
    }
    if (strideOut) *strideOut = stride;
    return addr;
}

// Discover the global Faction slot index from an entity whose faction value we
// already know (the local player, value 7).
//
// A candidate must satisfy all of:
//   * one byte wide
//   * present on this entity
//   * value == `knownValue`
//   * value within the 16-value FactionType range (guards against a level byte
//     that also happens to read 7)
//
// Several one-byte components can read 7 at the same moment, so this returns a
// list rather than one index. `ConfirmFactionByChange` is how a caller narrows
// it down to one.
inline int FactionCandidates(const EntityRef& e, uint8_t knownValue,
                             int* out, int max) {
    int slots[64];
    const int total = ByteSlots(reinterpret_cast<const uint8_t*>(e.def), slots, 64);
    int n = 0;
    for (int i = 0; i < total && i < 64; ++i) {
        uint8_t v = 0xFF;
        if (!ReadSlot(e, slots[i], &v, 1)) continue;
        if (v != knownValue) continue;
        if (v > kFactionServerMax) continue;
        if (out && n < max) out[n] = slots[i];
        ++n;
    }
    return n;
}

} // namespace wolfmount::mgr
