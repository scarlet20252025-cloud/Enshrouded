// ============================================================================
//  WolfMount — live entity operations (implementation)
//
//  See entityops.h for why there is no Create hook and how the Faction slot is
//  identified by its values rather than its name.
// ============================================================================

#include "entityops.h"

#include "entitymgr.h"
#include "faction.h"
#include "gamedata.h"
#include "gamehooks.h"
#include "layout.h"
#include "logging.h"

#include <windows.h>

#include <atomic>
#include <cmath>
#include <cstring>

namespace wolfmount::entityops {

namespace {

// RVA of the entity factory. Verified against our image:
//   SPAWN_CREATE signature (40 bytes) matches exactly once at RVA 0x97B790.
// Its prologue is
//   mov [rsp+0x20], r9 ; mov [rsp+0x18], r8 ; mov [rsp+0x10], edx
//   mov [rsp+0x08], rcx ; push rbp ; push rsi ; push r12 ; push r14
//   lea rbp,[rsp-0xdd8] ; sub rsp,0xed8
// i.e. a plain win64 function: u32 Create(void* manager, u32 kind, void* desc,
// void* arg4). No special calling convention is needed to call it.
constexpr uint32_t kSpawnCreateRva = 0x97B790;

// Component hashes we write when spawning. Both verified against the
// reflection table and against the community mod's independent constants.
constexpr uint32_t kHashCurrentTransform = 0x027AC564;
constexpr uint32_t kHashOverrideLevel    = 0xA21E7EE7;

// CurrentTransform is 3 x int64 fixed-point position, then 4 float32s.
constexpr size_t kTransformSize = 56;

using CreateFn = uint32_t (*)(void* manager, uint32_t kind, void* desc, void* arg4);

std::atomic<uintptr_t> g_manager{0};
std::atomic<int>       g_factionSlot{-1};
std::atomic<uint32_t>  g_playerId{0};
std::atomic<int>       g_lastScanSize{0};
std::atomic<int>       g_discoverAttempts{0};
std::atomic<int>       g_dumpCount{0};

uintptr_t GameBase() {
    static HMODULE s_mod = nullptr;
    if (!s_mod) {
        s_mod = GetModuleHandleA("enshrouded.exe");
        if (!s_mod) s_mod = GetModuleHandleA("enshrouded_server.exe");
    }
    return reinterpret_cast<uintptr_t>(s_mod);
}

// Build an EntityRef for `id`, or return false.
bool Lookup(uint32_t id, mgr::EntityRef* ref) {
    const uintptr_t m = g_manager.load(std::memory_order_relaxed);
    if (!m || id == 0) return false;
    return mgr::Find(m, id, ref);
}

// A candidate manager is the object whose +0x148 validates as the entity map
// AND whose +0x00 is a readable pointer — that second half is what the entity
// factory dereferences first (`movq (%rcx),%rsi` at RVA 0x97B7B8), so a
// candidate without it would fault the moment we tried to spawn through it.
bool TryManager(uintptr_t candidate, const char* where) {
    if (candidate < 0x10000) return false;
    mgr::MapHeader h;
    if (!mgr::ReadHeader(candidate, &h)) return false;

    // A real map holds entities; a count of 0 during play means we found an
    // uninitialised lookalike.
    if (h.count == 0) return false;

    // Plausibility: capacity must be able to hold the count, and the count must
    // be a sane number for a single-player world.
    if (h.capacity < h.count) return false;
    if (h.count > (1u << 20)) return false;

    // Shape check for the spawn path: [candidate] must be a readable pointer.
    uintptr_t world = 0;
    if (!layout::Read(candidate, &world, 8) || world < 0x10000) return false;

    // Every probe that got this far has the same map signature, so a second
    // success means we cannot tell them apart. Refuse rather than pick one at
    // random: a wrong manager would put faction writes on unrelated bytes.
    const uintptr_t already = g_manager.load(std::memory_order_relaxed);
    if (already && already != candidate) {
        WM_MOD_LOG("[wolfmount/entity] manager candidate conflict: already %p, "
                   "now %p via %s — keeping the first",
                   reinterpret_cast<void*>(already),
                   reinterpret_cast<void*>(candidate), where);
        return true;
    }

    g_manager.store(candidate, std::memory_order_relaxed);
    WM_MOD_LOG("[wolfmount/entity] manager resolved via %s: %p "
               "(count=%u capacity=%llu world=%p server=%d)",
               where, reinterpret_cast<void*>(candidate), h.count,
               (unsigned long long)h.capacity,
               reinterpret_cast<void*>(world),
               mgr::IsServerManager(candidate) ? 1 : 0);
    return true;
}

// Probe one root object: the object itself, then every aligned pointer it holds
// in its first 0x200 bytes. Bounded and read-guarded, so a stale or wrong root
// costs nothing.
bool ProbeRoot(uintptr_t root, const char* label) {
    if (root < 0x10000) return false;
    if (TryManager(root, label)) return true;

    for (size_t off = 0; off < 0x200; off += 8) {
        uintptr_t candidate = 0;
        if (!layout::Read(root + off, &candidate, 8)) break;
        if (TryManager(candidate, label)) return true;
    }
    return false;
}

} // namespace

const uint8_t kPlayerGuid[16] = {
    0xc3, 0xdb, 0x66, 0xd6, 0x89, 0xa5, 0x4a, 0x6c,
    0xa8, 0xe3, 0xd9, 0xa1, 0xf6, 0x00, 0x98, 0x12,
};

namespace {

int HexDigit(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// Templates we have actually seen in the shipped data with
// tools/tpl_guid.py, so `spawn` can be driven by a readable name. Each GUID is
// the raw UUID of its TemplateResource file; the note records what the template
// is, since that is the part a caller needs to choose between them.
const NamedTemplate kTemplates[] = {
    {"wolf",        "478381c5-585f-4264-b373-dbb1ea596eca",
     "Enemy_Wildbeast_wolf_earlygame — the early-game wolf, faction WildBeast"},
    {"wolf_heavy",  "f6a96b72-6da4-4e04-ab62-40e8d0feeac7",
     "Enemy_Wildbeast_Wolf_Heavy — the stronger wolf"},
    {"wolf_boss",   "ca98115b-71a2-4de2-9418-cf8d34b75ce3",
     "Enemy_Wildbeast_Wolf_Heavy_BossHealthBar — heavy wolf with a boss bar"},
    {"dog",         "5d9c1829-69fc-4339-8bcc-5e62e63e9a31",
     "Animal_Wildlife_Dog_01_bright_AG2 — a real tameable animal (Animal+Wildlife)"},
    {"player",      "c3db66d6-89a5-4a6c-a8e3-d9a1f6009812",
     "1_Player — the local player template (do NOT spawn; reference only)"},
};

} // namespace

bool ParseGuid(const char* text, uint8_t out[16]) {
    if (!text || !out) return false;
    uint8_t buf[16];
    int n = 0;
    for (const char* p = text; *p; ++p) {
        if (*p == '-' || *p == ' ' || *p == '\t') continue;
        const int hi = HexDigit(*p);
        if (hi < 0) return false;
        ++p;
        while (*p == '-') ++p;   // tolerate "ab-cd" groups
        if (!*p) return false;
        const int lo = HexDigit(*p);
        if (lo < 0) return false;
        if (n >= 16) return false;    // too many digits
        buf[n++] = static_cast<uint8_t>((hi << 4) | lo);
    }
    if (n != 16) return false;
    memcpy(out, buf, 16);
    return true;
}

void FormatGuid(const uint8_t guid[16], char out[37]) {
    if (!guid || !out) return;
    static const char kHex[] = "0123456789abcdef";
    int w = 0;
    for (int i = 0; i < 16; ++i) {
        if (i == 4 || i == 6 || i == 8 || i == 10) out[w++] = '-';
        out[w++] = kHex[guid[i] >> 4];
        out[w++] = kHex[guid[i] & 0x0F];
    }
    out[w] = '\0';
}

const NamedTemplate* Templates(int* count) {
    if (count) *count = static_cast<int>(sizeof(kTemplates) / sizeof(kTemplates[0]));
    return kTemplates;
}

const NamedTemplate* LookupTemplate(const char* name) {
    if (!name) return nullptr;
    for (const auto& t : kTemplates) {
        if (strcmp(t.name, name) == 0) return &t;
    }
    return nullptr;
}

bool HasManager() { return g_manager.load(std::memory_order_relaxed) != 0; }
void* Manager() { return reinterpret_cast<void*>(g_manager.load(std::memory_order_relaxed)); }

bool ResolveManager() {
    if (HasManager()) return true;

    // The manager is one member of the aggregate the game calls the world
    // context, but exactly which one differs between a fresh load and a map
    // change, so probe the object and every pointer it holds.
    if (void* ctx = gamehooks::WorldContext()) {
        if (ProbeRoot(reinterpret_cast<uintptr_t>(ctx), "world context")) {
            return true;
        }
    }

    // The world holder's [0] is the ECS world — a different object again.
    if (void* holder = gamehooks::WorldHolder()) {
        uintptr_t world = 0;
        if (layout::Read(reinterpret_cast<uintptr_t>(holder), &world, 8) &&
            ProbeRoot(world, "world")) {
            return true;
        }
    }

    // Log the failure once every few seconds rather than every frame.
    const int n = g_discoverAttempts.fetch_add(1) + 1;
    if (n == 1 || (n % 600) == 0) {
        WM_MOD_LOG("[wolfmount/entity] manager NOT found yet (attempt %d, ctx %p). "
                   "Is a world loaded?", n, gamehooks::WorldContext());
    }
    return false;
}

int EntityCount() {
    const uintptr_t m = g_manager.load(std::memory_order_relaxed);
    if (!m) return 0;
    mgr::MapHeader h;
    if (!mgr::ReadHeader(m, &h)) return 0;
    return static_cast<int>(h.count);
}

int ListEntities(uint32_t* out, int max) {
    const uintptr_t m = g_manager.load(std::memory_order_relaxed);
    if (!m) return 0;
    return mgr::EnumerateIds(m, out, max);
}

int LastScanSize() { return g_lastScanSize.load(std::memory_order_relaxed); }

// ---------------------------------------------------------------------------
//  Faction slot discovery
//
//  The hard part is not finding a byte that says 7 — several will. It is proving
//  which byte is Faction. The proof is behavioural: only Faction changes when we
//  change it, and only Faction spans the exact value set {0..15} across the
//  varied population of a live world.
//
//  So the discovery pass does three things:
//    1. Enumerate every live entity and, for each, every one-byte slot.
//    2. Record, per slot, the set of values seen and how many entities had it.
//    3. A slot is accepted only if every value it ever showed is in [0,15], it
//       is present on a large share of entities, and it showed at least three
//       distinct values (a constant is not a faction).
// ---------------------------------------------------------------------------

namespace {

constexpr int kMaxEntitiesForDiscovery = 4000;
constexpr int kMaxSlots = 640;
constexpr int kMaxDistinct = 24;

struct SlotStats {
    int  present = 0;
    bool outOfRange = false;      // ever read a value > 15
    uint8_t distinct[kMaxDistinct] = {0};
    int  distinctCount = 0;
};

void NoteValue(SlotStats* s, uint8_t v) {
    ++s->present;
    if (v > faction::Ancients) { s->outOfRange = true; return; }
    for (int i = 0; i < s->distinctCount; ++i) {
        if (s->distinct[i] == v) return;
    }
    if (s->distinctCount < kMaxDistinct) s->distinct[s->distinctCount++] = v;
}

} // namespace

int DiscoverFactionSlot() {
    if (g_factionSlot.load(std::memory_order_relaxed) >= 0) {
        return g_factionSlot.load(std::memory_order_relaxed);
    }
    if (!ResolveManager()) return -1;

    const uintptr_t m = g_manager.load(std::memory_order_relaxed);
    mgr::MapHeader h;
    if (!mgr::ReadHeader(m, &h)) return -1;

    // Collect ids first: we need repeated passes over the same set.
    static uint32_t ids[kMaxEntitiesForDiscovery];
    int n = mgr::EnumerateIds(m, ids, kMaxEntitiesForDiscovery);
    if (n < 8) {
        WM_MOD_LOG("[wolfmount/entity] faction discovery deferred: only %d "
                   "entities live", n);
        return -1;
    }

    static SlotStats stats[kMaxSlots];
    memset(stats, 0, sizeof(stats));

    int sampled = 0;
    for (int i = 0; i < n; ++i) {
        mgr::EntityRef ref;
        if (!mgr::Find(m, ids[i], &ref)) continue;
        ++sampled;

        const auto* def = reinterpret_cast<const uint8_t*>(ref.def);
        for (int slot = 0; slot < kMaxSlots; ++slot) {
            uintptr_t addr = 0;
            uint16_t stride = 0;
            if (!layout::SlotAddress(def, ref.chunk, ref.slot, slot, &addr,
                                     &stride)) {
                continue;
            }
            if (stride != 1) continue;
            uint8_t v = 0xFF;
            if (!layout::Read(addr, &v, 1)) continue;
            NoteValue(&stats[slot], v);
        }
    }

    // Gather candidates, then pick the best one.
    struct Cand { int slot; int present; int distinct; };
    Cand best{-1, 0, 0};
    Cand second{-1, 0, 0};
    int candidates = 0;

    for (int slot = 0; slot < kMaxSlots; ++slot) {
        const SlotStats& s = stats[slot];
        if (s.present == 0 || s.outOfRange) continue;
        if (s.distinctCount < 3) continue;
        // Must appear on a substantial share of the population; a rare flag that
        // happens to be small is not a faction.
        if (s.present * 10 < sampled * 3) continue;   // >= 30% of entities
        ++candidates;
        const Cand c{slot, s.present, s.distinctCount};
        if (c.present > best.present) {
            second = best;
            best = c;
        } else if (c.present > second.present) {
            second = c;
        }
    }

    if (best.slot < 0) {
        WM_MOD_LOG("[wolfmount/entity] faction slot NOT found "
                   "(sampled %d entities, %d candidates)", sampled, candidates);
        return -1;
    }

    // The winner must be clearly ahead of the runner-up. When two slots tie,
    // reporting the wrong one would silently apply faction writes to an
    // unrelated byte, so refuse instead of guessing.
    if (second.slot >= 0 && second.present * 10 > best.present * 9) {
        WM_MOD_LOG("[wolfmount/entity] faction slot ambiguous: slot %d "
                   "(present %d) vs slot %d (present %d) among %d candidates "
                   "over %d entities — NOT adopting either",
                   best.slot, best.present, second.slot, second.present,
                   candidates, sampled);
        return -1;
    }

    g_factionSlot.store(best.slot, std::memory_order_relaxed);
    g_lastScanSize.store(sampled, std::memory_order_relaxed);

    const SlotStats& s = stats[best.slot];
    char vals[128] = {0};
    for (int i = 0; i < s.distinctCount && i < kMaxDistinct; ++i) {
        char one[8];
        snprintf(one, sizeof(one), "%s%u", i ? "," : "", (unsigned)s.distinct[i]);
        strncat(vals, one, sizeof(vals) - strlen(vals) - 1);
    }
    WM_MOD_LOG("[wolfmount/entity] faction slot = %d "
               "(present on %d/%d entities, values seen {%s})",
               best.slot, s.present, sampled, vals);
    return best.slot;
}

int FactionSlot() { return g_factionSlot.load(std::memory_order_relaxed); }

int ReadFaction(uint32_t entityId) {
    const int slot = FactionSlot();
    if (slot < 0) return -1;
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) return -1;
    uint8_t v = 0xFF;
    if (!mgr::ReadSlot(ref, slot, &v, 1)) return -1;
    return v;
}

bool WriteFaction(uint32_t entityId, uint8_t value) {
    const int slot = FactionSlot();
    if (slot < 0) {
        WM_MOD_LOG("[wolfmount/entity] WriteFaction(%u) refused: faction slot "
                   "not discovered yet", entityId);
        return false;
    }
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) {
        WM_MOD_LOG("[wolfmount/entity] WriteFaction(%u) refused: entity not live",
                   entityId);
        return false;
    }

    const uint8_t before = [&] {
        uint8_t v = 0xFF;
        mgr::ReadSlot(ref, slot, &v, 1);
        return v;
    }();

    if (!mgr::WriteSlot(ref, slot, &value, 1)) {
        WM_MOD_LOG("[wolfmount/entity] WriteFaction(%u) failed: slot %d not "
                   "writable", entityId, slot);
        return false;
    }

    const uint8_t after = [&] {
        uint8_t v = 0xFF;
        mgr::ReadSlot(ref, slot, &v, 1);
        return v;
    }();

    const bool ok = (after == value);
    WM_MOD_LOG("[wolfmount/entity] FACTION %u: %u(%s) -> %u(%s) slot=%d "
               "verified=%d", entityId, (unsigned)before,
               game::FactionName(before), (unsigned)after,
               game::FactionName(after), slot, ok ? 1 : 0);
    return ok;
}

uint32_t PlayerEntityId() {
    const uint32_t cached = g_playerId.load(std::memory_order_relaxed);
    if (cached) {
        mgr::EntityRef ref;
        if (Lookup(cached, &ref)) return cached;
        g_playerId.store(0, std::memory_order_relaxed);
    }

    const int slot = FactionSlot();
    if (slot < 0) return 0;

    static uint32_t ids[4096];
    const int n = ListEntities(ids, 4096);
    for (int i = 0; i < n; ++i) {
        const int f = ReadFaction(ids[i]);
        if (f == faction::Player) {
            g_playerId.store(ids[i], std::memory_order_relaxed);
            WM_MOD_LOG("[wolfmount/entity] player entity = %u (faction Player)",
                       ids[i]);
            return ids[i];
        }
    }
    return 0;
}

namespace {

// Position slot is discovered the same way Faction is: by shape. A 56-byte
// component whose first three int64s convert to a plausible world position is
// CurrentTransform. Enshrouded's playable area is well under 100 km across, so
// |x|,|y|,|z| < 200000 metres is a very safe bound.
constexpr double kMaxPlausibleMeters = 200000.0;

int FindTransformSlot(uint32_t entityId) {
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) return -1;
    const auto* def = reinterpret_cast<const uint8_t*>(ref.def);

    for (int slot = 0; slot < kMaxSlots; ++slot) {
        uintptr_t addr = 0;
        uint16_t stride = 0;
        if (!layout::SlotAddress(def, ref.chunk, ref.slot, slot, &addr,
                                 &stride)) {
            continue;
        }
        if (stride != kTransformSize) continue;
        int64_t pos[3] = {0, 0, 0};
        if (!layout::Read(addr, pos, sizeof(pos))) continue;
        bool plausible = true;
        for (int k = 0; k < 3; ++k) {
            const double m = layout::FixedToMeters(pos[k]);
            if (!std::isfinite(m) || std::fabs(m) > kMaxPlausibleMeters) {
                plausible = false;
                break;
            }
        }
        if (!plausible) continue;
        // Not the origin: an unwritten transform reads all zeros, which is
        // outside the playable map.
        if (pos[0] == 0 && pos[1] == 0 && pos[2] == 0) continue;
        return slot;
    }
    return -1;
}

} // namespace

bool PlayerPosition(double* x, double* y, double* z) {
    const uint32_t pid = PlayerEntityId();
    if (!pid) return false;
    const int slot = FindTransformSlot(pid);
    if (slot < 0) return false;
    mgr::EntityRef ref;
    if (!Lookup(pid, &ref)) return false;
    uintptr_t addr = mgr::SlotAddressOf(ref, slot);
    if (!addr) return false;
    int64_t pos[3] = {0, 0, 0};
    if (!layout::Read(addr, pos, sizeof(pos))) return false;
    if (x) *x = layout::FixedToMeters(pos[0]);
    if (y) *y = layout::FixedToMeters(pos[1]);
    if (z) *z = layout::FixedToMeters(pos[2]);
    return true;
}

int ListWildBeasts(uint32_t* out, int max) {
    const int slot = FactionSlot();
    if (slot < 0) return 0;
    static uint32_t ids[8192];
    const int n = ListEntities(ids, 8192);
    int written = 0;
    for (int i = 0; i < n; ++i) {
        if (ReadFaction(ids[i]) != faction::WildBeast) continue;
        if (out && written < max) out[written] = ids[i];
        ++written;
        if (out && written >= max) break;
    }
    return written;
}

bool ReadComponent(uint32_t entityId, int slot, void* buf, uint16_t stride) {
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) return false;
    return mgr::ReadSlot(ref, slot, buf, stride);
}

bool WriteComponent(uint32_t entityId, int slot, const void* data,
                    uint16_t stride) {
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) return false;
    if (!mgr::WriteSlot(ref, slot, data, stride)) return false;
    // Verify by read-back; a write that did not stick is not a success.
    uint8_t back[256];
    const uint16_t n = stride < sizeof(back) ? stride : (uint16_t)sizeof(back);
    if (!mgr::ReadSlot(ref, slot, back, stride)) return false;
    return memcmp(back, data, n) == 0;
}

uintptr_t ComponentAddress(uint32_t entityId, int slot, uint16_t* strideOut) {
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) return 0;
    return mgr::SlotAddressOf(ref, slot, strideOut);
}

uint32_t SpawnAt(const uint8_t guid[16], double x, double y, double z,
                 uint32_t level) {
    if (!guid) return 0;
    const uintptr_t m = g_manager.load(std::memory_order_relaxed);
    if (!m) {
        WM_MOD_LOG("[wolfmount/spawn] refused: entity manager not resolved");
        return 0;
    }
    const uintptr_t base = GameBase();
    if (!base) {
        WM_MOD_LOG("[wolfmount/spawn] refused: game module not found");
        return 0;
    }
    const auto create = reinterpret_cast<CreateFn>(base + kSpawnCreateRva);
    if (!create) return 0;

    // CurrentTransform: three fixed-point int64s then four float32s.
    alignas(16) uint8_t transform[kTransformSize] = {0};
    const int64_t ix = layout::MetersToFixed(x);
    const int64_t iy = layout::MetersToFixed(y);
    const int64_t iz = layout::MetersToFixed(z);
    memcpy(transform + 0,  &ix, 8);
    memcpy(transform + 8,  &iy, 8);
    memcpy(transform + 16, &iz, 8);
    const float one = 1.0f;
    memcpy(transform + 36, &one, 4);
    memcpy(transform + 40, &one, 4);
    memcpy(transform + 44, &one, 4);
    memcpy(transform + 48, &one, 4);

    uint32_t levelValue = level;

    // Component descriptor array: 24 bytes per entry.
    //   +0x00 u32 hash
    //   +0x08 void* data
    //   +0x10 u64 size
    alignas(16) uint8_t entries[0x40] = {0};
    const uint32_t nEntries = 2;
    memcpy(entries + 0,  &kHashCurrentTransform, 4);
    uint64_t p = reinterpret_cast<uint64_t>(transform);
    memcpy(entries + 8,  &p, 8);
    uint64_t sz = kTransformSize;
    memcpy(entries + 16, &sz, 8);
    memcpy(entries + 24, &kHashOverrideLevel, 4);
    p = reinterpret_cast<uint64_t>(&levelValue);
    memcpy(entries + 32, &p, 8);
    sz = 4;
    memcpy(entries + 40, &sz, 8);

    // Spawn descriptor.
    //   +0x04  template GUID (16 bytes)
    //   +0x18  component array pointer
    //   +0x20  component count
    alignas(16) uint8_t desc[0x40] = {0};
    memcpy(desc + 4, guid, 16);
    p = reinterpret_cast<uint64_t>(entries);
    memcpy(desc + 0x18, &p, 8);
    uint64_t count = nEntries;
    memcpy(desc + 0x20, &count, 8);

    const uint32_t id = create(reinterpret_cast<void*>(m), 0, desc, nullptr);

    WM_MOD_LOG("[wolfmount/spawn] create(guid %02x%02x%02x%02x...) at "
               "(%.1f, %.1f, %.1f) level %u -> entity %u",
               guid[0], guid[1], guid[2], guid[3], x, y, z, level, id);
    return id;
}

int SpawnNearPlayer(const uint8_t guid[16], int count, double distance,
                    uint32_t level) {
    double x = 0, y = 0, z = 0;
    if (!PlayerPosition(&x, &y, &z)) {
        WM_MOD_LOG("[wolfmount/spawn] refused: player position not available");
        return 0;
    }
    if (count < 1) count = 1;
    if (count > 8) count = 8;
    if (distance < 0.5) distance = 0.5;

    int spawned = 0;
    for (int i = 0; i < count; ++i) {
        const double angle = 2.0 * 3.14159265358979323846 * i / count;
        const double sx = x + distance * std::cos(angle);
        const double sz = z + distance * std::sin(angle);
        const uint32_t id = SpawnAt(guid, sx, y + 0.5, sz, level);
        if (id == 0) continue;
        // Verify the entity is actually in the manager; the factory returning a
        // non-zero id is not the same as a live entity.
        mgr::EntityRef ref;
        if (Lookup(id, &ref)) ++spawned;
    }
    WM_MOD_LOG("[wolfmount/spawn] requested %d, verified live %d", count,
               spawned);
    return spawned;
}

void DumpEntity(uint32_t entityId, int maxSlots) {
    const int n = g_dumpCount.fetch_add(1) + 1;
    if (n > 6) return;   // bounded: this is a diagnostic, not a trace

    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) {
        WM_MOD_LOG("[wolfmount/dump] entity %u not live", entityId);
        return;
    }
    WM_MOD_LOG("[wolfmount/dump] #%d entity %u def=%p chunk=%p slot=%u",
               n, entityId, reinterpret_cast<void*>(ref.def),
               reinterpret_cast<void*>(ref.chunk), ref.slot);

    const auto* def = reinterpret_cast<const uint8_t*>(ref.def);
    int shown = 0;
    for (int slot = 0; slot < kMaxSlots && shown < maxSlots; ++slot) {
        uintptr_t addr = 0;
        uint16_t stride = 0;
        if (!layout::SlotAddress(def, ref.chunk, ref.slot, slot, &addr,
                                 &stride)) {
            continue;
        }
        uint8_t buf[32] = {0};
        const uint16_t take = stride < sizeof(buf) ? stride : (uint16_t)sizeof(buf);
        if (!layout::Read(addr, buf, take)) continue;

        char hex[3 * 32 + 1] = {0};
        for (int i = 0; i < take && i < 24; ++i) {
            snprintf(hex + i * 3, sizeof(hex) - i * 3, "%02x ", buf[i]);
        }
        WM_MOD_LOG("[wolfmount/dump]   slot %3d stride %3u addr %p  %s",
                   slot, stride, reinterpret_cast<void*>(addr), hex);
        ++shown;
    }
}

} // namespace wolfmount::entityops
