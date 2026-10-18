// ============================================================================
//  WolfMount — entity component layout (read-only memory model)
//
//  Ported from the community mod "M182 Admin Pannel" (GPL-3.0) and verified
//  against our own image. This is the piece WolfMount was missing for three
//  releases.
//
//  WHY WE ARE HERE
//  ----------------
//  Every attempt to change a component value went through `Enqueue`, the queue
//  the game uses when IT writes a component. That worked for exactly one thing
//  (IsTame) and silently did nothing for Faction, because Faction has no Enqueue
//  call site in the image at all — it is written by a different channel.
//
//  The alternative is to stop asking the engine for permission and simply look
//  at where the component already lives in memory. The engine already stores
//  every instance of every component in a flat chunk, and it keeps a table that
//  says which components an entity definition has and where each one sits. That
//  table is readable, so a component's address is a pure offset calculation.
//
//      entity definition object:
//          +0x0000  u64 bitmap[10]   which of the 640 component slots exist
//          +0x0084  u16 offset[640]  byte offset of the slot inside the chunk
//          +0x0a84  u16 stride[640]  size in bytes of ONE instance
//
//      chunk + offset[slot] + stride[slot] * index  ==  that instance
//
//  The player entity's CurrentTransform, a wolf's Faction byte, health, damage
//  — all of them become ordinary readable/writable memory. No queues, no
//  events, no guessing where a payload starts.
// ============================================================================

#pragma once

#include <windows.h>

#include <cstdint>
#include <cstring>

namespace wolfmount::layout {

// How many component slots an entity definition can describe. The engine's
// tables are exactly this long.
constexpr int kComponentSlots = 640;

// Size of the component table at the head of an entity definition.
constexpr size_t kTableBytes = 0xf90;

// Size of a CurrentTransform component: 3 x int64 fixed-point position
// followed by 4 float32s. 1.0 fixed-point unit == 1/2^32 metres, so positions
// reach +-2^31 metres with sub-micrometre precision.
constexpr size_t kCurrentTransformSize = 56;

// int64 <-> metres conversion for the fixed-point coordinates.
constexpr double kMetersPerUnit = 4294967296.0;   // 2^32

inline int64_t MetersToFixed(double m) {
    // Widen first so we keep sub-metre precision before the truncating cast.
    return static_cast<int64_t>(m * kMetersPerUnit);
}

inline double FixedToMeters(int64_t v) {
    return static_cast<double>(v) / kMetersPerUnit;
}

// A readable 64-bit little-endian value. The engine is little-endian on every
// platform it ships on, so a straight load is correct — but go through these
// helpers so the assumption is stated once.
inline uint64_t Load64(const uint8_t* p) {
    uint64_t v;
    memcpy(&v, p, 8);
    return v;
}

inline uint32_t Load32(const uint8_t* p) {
    uint32_t v;
    memcpy(&v, p, 4);
    return v;
}

inline uint16_t Load16(const uint8_t* p) {
    uint16_t v;
    memcpy(&v, p, 2);
    return v;
}

// Is there a component of slot `index` in this definition?
inline bool HasSlot(const uint8_t* def, int index) {
    if (!def || index < 0 || index >= kComponentSlots) return false;
    const uint64_t word = Load64(def + (index >> 6) * 8);
    return ((word >> (index & 63)) & 1) != 0;
}

// Where does slot `index` live for the instance at `index` inside the chunk?
// Returns false when the slot is absent or has zero stride (a present slot with
// stride 0 carries no storage — skip it rather than compute a nonsense address).
inline bool SlotAddress(const uint8_t* def, uintptr_t chunk, uint32_t slot,
                        int index, uintptr_t* outAddr, uint16_t* outStride) {
    if (!outAddr) return false;
    if (!HasSlot(def, index)) return false;
    const uint16_t offset = Load16(def + 0x84 + index * 2);
    const uint16_t stride = Load16(def + 0xa84 + index * 2);
    if (stride == 0) return false;
    *outAddr = chunk + offset + static_cast<size_t>(stride) * slot;
    if (outStride) *outStride = stride;
    return true;
}

// Read `len` bytes from `addr`. Returns false on any unreadable byte.
// ReadProcessMemory rather than a raw pointer read so a stale chunk from an
// entity that died last frame returns false instead of crashing the game.
inline bool Read(uintptr_t addr, void* out, size_t len) {
    if (addr < 0x10000 || len == 0 || !out) return false;
    SIZE_T got = 0;
    const BOOL ok = ReadProcessMemory(GetCurrentProcess(),
                                      reinterpret_cast<LPCVOID>(addr),
                                      out, len, &got);
    return ok && got == len;
}

inline bool Write(uintptr_t addr, const void* data, size_t len) {
    if (addr < 0x10000 || len == 0 || !data) return false;
    SIZE_T put = 0;
    const BOOL ok = WriteProcessMemory(GetCurrentProcess(),
                                       reinterpret_cast<LPVOID>(addr),
                                       const_cast<void*>(data), len, &put);
    return ok && put == len;
}

template <typename T>
inline bool Read(uintptr_t addr, T* out) {
    return Read(addr, out, sizeof(T));
}

template <typename T>
inline bool Write(uintptr_t addr, const T& value) {
    return Write(addr, &value, sizeof(T));
}

inline bool ReadBytes(uintptr_t addr, uint8_t* buf, size_t len) {
    return Read(addr, buf, len);
}

} // namespace wolfmount::layout
