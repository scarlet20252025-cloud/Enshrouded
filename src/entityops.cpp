// ============================================================================
//  WolfMount — live entity operations (implementation)
//
//  See entityops.h for why there is no Create hook and how the Faction slot is
//  identified by its values rather than its name.
// ============================================================================

#include "entityops.h"

#include "entitymgr.h"
#include "faction.h"
#include "followset.h"
#include "gamedata.h"
#include "gamehooks.h"
#include "layout.h"
#include "logging.h"

#include <windows.h>

#include <atomic>
#include <cmath>
#include <cstring>
#include <cstdint>

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
std::atomic<uint32_t>  g_routeAPlayer{0};
std::atomic<int>       g_lastScanSize{0};
std::atomic<int>       g_discoverAttempts{0};
std::atomic<int>       g_dumpCount{0};
// The most recent entity ever enrolled as a follower. Remembered separately
// from the live set so the mount button still works right after a death.
std::atomic<uint32_t>  g_lastFollower{0};

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

// How many entities are actually live. EnumerateIds() can report far fewer ids
// than EntityCount() suggests because the occupancy bitmap is sparse; and at
// 19k entities an 8192-slot caller buffer silently truncates the population, so
// a "wild beasts = 0" result may just mean the wolves were past the cut.
int ListEntitiesSized(uint32_t* out, int max) {
    return ListEntities(out, max);
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

// Discovery is O(entities x slots) ReadProcessMemory calls. At 4000 entities x
// 640 slots that is 2.5 MILLION syscalls, and because it ran every 240 frames
// while failing it was a major contributor to the stutter the user reported.
// 240 entities is plenty to prove a slot's value distribution and costs ~150k
// calls once.
constexpr int kMaxEntitiesForDiscovery = 240;
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

// The community mod identifies the player by shape, not by faction: the player
// is the entity whose definition carries a 40-byte component whose first u32 is
// the Stamina type hash. That works before Faction is known, which is exactly
// what we need here — it breaks the chicken-and-egg between "find the player"
// and "find Faction by looking at the player".
constexpr uint32_t kSignatureStamina = 0x04B6AA8B;
constexpr uint16_t kStaminaStride   = 40;

// A definition's slot tables, read in ONE ReadProcessMemory instead of 640.
// SlotAddress() re-reads the stride table for every slot it is asked about,
// which turned the player search into millions of syscalls.
struct DefTables {
    uint8_t raw[layout::kTableBytes] = {0};

    bool Load(uintptr_t def) {
        return layout::Read(def, raw, sizeof(raw));
    }
    bool Has(int slot) const {
        if (slot < 0 || slot >= layout::kComponentSlots) return false;
        const uint64_t word = layout::Load64(raw + (slot >> 6) * 8);
        return ((word >> (slot & 63)) & 1) != 0;
    }
    uint16_t Stride(int slot) const {
        return layout::Load16(raw + 0xa84 + slot * 2);
    }
    uint16_t Offset(int slot) const {
        return layout::Load16(raw + 0x84 + slot * 2);
    }
};

// Confirm on a live instance: a 40-byte slot whose first u32 equals the Stamina
// signature. Returns true and reports the slot index.
bool InstanceHasStamina(const mgr::EntityRef& ref, uintptr_t defCache,
                        const DefTables& t, int* foundSlot) {
    for (int slot = 0; slot < layout::kComponentSlots; ++slot) {
        if (!t.Has(slot)) continue;
        if (t.Stride(slot) != kStaminaStride) continue;
        const uintptr_t addr = ref.chunk + t.Offset(slot) +
                               static_cast<size_t>(kStaminaStride) * ref.slot;
        uint32_t sig = 0;
        if (!layout::Read(addr, &sig, 4)) continue;
        if (sig == kSignatureStamina) {
            if (foundSlot) *foundSlot = slot;
            return true;
        }
    }
    (void)defCache;
    return false;
}

// Route A: locate the player, then pick the one-byte slot reading 7 on it.
// Returns the slot index, or -1 when this route cannot decide.
int DiscoverFactionSlotViaPlayer(uintptr_t m, const uint32_t* ids, int n) {
    uint32_t playerId = 0;
    mgr::EntityRef playerRef;
    int staminaSlot = -1;

    // Def tables repeat across entities of the same template, so cache the last
    // one — the playable set has only a few hundred distinct definitions.
    uintptr_t cachedDef = 0;
    DefTables tables;

    // Fast path first. Every HitEvent we captured in an earlier session carried
    // sourceId == 1 for the local player's own attacks, and the Enqueue trace
    // shows id 1 writing 80-byte records continuously. Try that id before
    // scanning, because a 19k-entry table is easy to miss the player in.
    {
        mgr::EntityRef ref;
        if (mgr::Find(m, 1, &ref) && tables.Load(ref.def) &&
            InstanceHasStamina(ref, ref.def, tables, &staminaSlot)) {
            playerId = 1;
            playerRef = ref;
            cachedDef = ref.def;
            WM_MOD_LOG("[wolfmount/entity] route A: entity 1 carries the "
                       "stamina signature (slot %d) — treating it as the "
                       "player", staminaSlot);
        }
    }

    for (int i = 0; i < n && !playerId; ++i) {
        if (ids[i] == 1) continue;                 // already tried
        mgr::EntityRef ref;
        if (!mgr::Find(m, ids[i], &ref)) continue;
        if (ref.def != cachedDef) {
            if (!tables.Load(ref.def)) continue;
            cachedDef = ref.def;
        }
        if (!InstanceHasStamina(ref, cachedDef, tables, &staminaSlot)) continue;
        playerId = ids[i];
        playerRef = ref;
    }
    if (!playerId) {
        WM_MOD_LOG("[wolfmount/entity] route A: no entity carries the stamina "
                   "signature among %d sampled — falling back to statistics", n);
        return -1;
    }
    WM_MOD_LOG("[wolfmount/entity] route A: player entity = %u (stamina slot "
               "%d)", playerId, staminaSlot);

    // Keep it. The stamina signature is a far stronger identity check than
    // "first entity whose one-byte slot reads 7", and PlayerEntityId() runs
    // before this discovery in some call orders — without this the later scan
    // would settle on a different entity (a production snapshot showed it
    // picking 6248 while route A had correctly found entity 1).
    g_routeAPlayer.store(playerId, std::memory_order_relaxed);

    // Every one-byte slot on the player that currently reads 7 (Player).
    int cands[64];
    const int nc = mgr::FactionCandidates(playerRef, faction::Player, cands, 64);
    WM_MOD_LOG("[wolfmount/entity] route A: player entity = %u, %d one-byte "
               "slots read 7", playerId, nc);

    if (nc == 1) {
        g_factionSlot.store(cands[0], std::memory_order_relaxed);
        g_lastScanSize.store(n, std::memory_order_relaxed);
        WM_MOD_LOG("[wolfmount/entity] faction slot = %d (route A: unique "
                   "one-byte slot reading 7 on the player)", cands[0]);
        // Do NOT cache `playerId` here. "The entity carrying a stamina signature"
        // is not necessarily the playable character: in production this matched
        // entity 1, while the entity whose Faction byte actually read Player was
        // 6426. Caching the wrong id would make every later lookup (position,
        // follow, mount) address a phantom. PlayerEntityId() re-derives it from
        // the faction slot, which is the authoritative answer.
        return cands[0];
    }
    if (nc == 0) return -1;

    // Several candidates: keep only those that also read a valid FactionType
    // value on a decent share of OTHER entities, which is what separates a
    // global component from a per-entity flag that happens to be 7.
    int bestSlot = -1;
    int bestHits = -1;
    for (int c = 0; c < nc; ++c) {
        const int slot = cands[c];
        int hits = 0;
        int bad = 0;
        for (int i = 0; i < n; ++i) {
            if (ids[i] == playerId) continue;
            mgr::EntityRef ref;
            if (!mgr::Find(m, ids[i], &ref)) continue;
            uint8_t v = 0xFF;
            if (!mgr::ReadSlot(ref, slot, &v, 1)) continue;
            if (v > faction::Ancients) { ++bad; continue; }
            ++hits;
        }
        // A real Faction component is present on most entities and never leaves
        // the enum range. A coincidental flag usually fails one of the two.
        if (bad > hits / 4) continue;
        if (hits > bestHits) { bestHits = hits; bestSlot = slot; }
    }

    if (bestSlot < 0) {
        WM_MOD_LOG("[wolfmount/entity] route A: %d candidate slots, none "
                   "survived the population check", nc);
        return -1;
    }

    g_factionSlot.store(bestSlot, std::memory_order_relaxed);
    g_lastScanSize.store(n, std::memory_order_relaxed);
    g_playerId.store(playerId, std::memory_order_relaxed);
    WM_MOD_LOG("[wolfmount/entity] faction slot = %d (route A: %d candidates, "
               "chose the one present on %d/%d other entities)",
               bestSlot, nc, bestHits, n - 1);
    return bestSlot;
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

    // Collect ids first: we need repeated passes over the same set. The player
    // can be anywhere in a table of 19k+ entities, so the sample must be large
    // enough to reach it — 240 was not, and Route A never saw the player.
    static uint32_t ids[kMaxEntitiesForDiscovery];
    int n = mgr::EnumerateIds(m, ids, kMaxEntitiesForDiscovery);
    if (n < 8) {
        WM_MOD_LOG("[wolfmount/entity] faction discovery deferred: only %d "
                   "entities live", n);
        return -1;
    }

    // -------------------------------------------------------------------
    //  Route A (the one the community mod actually uses): find the player
    //  entity first, then look for the one-byte slot that reads 7 on it.
    //
    //  Route B (statistical) is kept as a fallback but it has a fatal weakness
    //  we hit in production: it requires the candidate slot to appear on >=30%
    //  of entities AND show >=3 distinct values. An entity manager holding
    //  19455 mostly-world-prop entities satisfies neither, so it reported
    //  "0 candidates" forever even though Faction certainly existed.
    //
    //  Route A is far more direct: the player's faction byte IS 7 by
    //  definition, and a one-byte component reading exactly 7 on the player is
    //  a very short list.
    // -------------------------------------------------------------------
    if (int viaPlayer = DiscoverFactionSlotViaPlayer(m, ids, n); viaPlayer >= 0) {
        return viaPlayer;
    }

    static SlotStats stats[kMaxSlots];
    memset(stats, 0, sizeof(stats));

    int sampled = 0;
    int resolvedSlots = 0;      // SlotAddress() succeeded
    int strideOneSlots = 0;     // ... and the component is exactly one byte
    int unreadableSlots = 0;    // resolved but ReadProcessMemory failed
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
            ++resolvedSlots;
            if (stride != 1) continue;
            ++strideOneSlots;
            uint8_t v = 0xFF;
            if (!layout::Read(addr, &v, 1)) { ++unreadableSlots; continue; }
            NoteValue(&stats[slot], v);
        }
    }

    WM_MOD_LOG("[wolfmount/entity] faction scan: %d entities, %d slot addresses "
               "resolved, %d one-byte, %d unreadable",
               sampled, resolvedSlots, strideOneSlots, unreadableSlots);

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
        // Report the near-miss detail instead of just "nothing found": the most
        // useful fact is how many one-byte slots existed at all and what the
        // best few looked like. Without this the failure is undiagnosable.
        WM_MOD_LOG("[wolfmount/entity] faction slot NOT found "
                   "(sampled %d entities, %d candidates)", sampled, candidates);
        for (int slot = 0, shown = 0; slot < kMaxSlots && shown < 6; ++slot) {
            const SlotStats& s = stats[slot];
            if (s.present == 0) continue;
            char vals[96] = {0};
            for (int i = 0; i < s.distinctCount && i < kMaxDistinct; ++i) {
                char one[8];
                snprintf(one, sizeof(one), "%s%u", i ? "," : "",
                         (unsigned)s.distinct[i]);
                strncat(vals, one, sizeof(vals) - strlen(vals) - 1);
            }
            WM_MOD_LOG("[wolfmount/entity]   1-byte slot %d: present %d/%d, "
                       "distinct %d {%s}%s", slot, s.present, sampled,
                       s.distinctCount, vals,
                       s.outOfRange ? " OUT-OF-RANGE" : "");
            ++shown;
        }
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

// Defined below (needs the DefTables helper). Declared inside an anonymous
// namespace so it refers to the same internal-linkage function that is defined
// there; declaring it at this scope would create a *different*, unresolved
// overload.
namespace {
int FindTransformSlot(uint32_t entityId);
}  // namespace

uint32_t PlayerEntityId() {
    // Route A already identified the character by the stamina signature, which
    // is a positive identification rather than a search heuristic. Trust it
    // first: searching by "first faction==Player" can land on a different live
    // entity (a production run picked 6248 while route A had found entity 1).
    const uint32_t known = g_routeAPlayer.load(std::memory_order_relaxed);
    if (known) {
        mgr::EntityRef ref;
        if (Lookup(known, &ref)) {
            const uint32_t cached = g_playerId.load(std::memory_order_relaxed);
            if (cached != known) {
                g_playerId.store(known, std::memory_order_relaxed);
                WM_MOD_LOG("[wolfmount/entity] player entity = %u (identified "
                           "by the stamina signature)", known);
            }
            return known;
        }
        // The entity is gone (respawn / level change). Drop the hint so the
        // search below can find the new one.
        g_routeAPlayer.store(0, std::memory_order_relaxed);
        g_playerId.store(0, std::memory_order_relaxed);
    }

    const uint32_t cached = g_playerId.load(std::memory_order_relaxed);
    if (cached) {
        mgr::EntityRef ref;
        if (Lookup(cached, &ref)) return cached;
        g_playerId.store(0, std::memory_order_relaxed);
    }

    const int slot = FactionSlot();
    if (slot < 0) return 0;

    // More than one live entity can carry Faction == Player: a production
    // snapshot showed Player=2. Picking the first by id gave an entity whose
    // position could not be read at all, so choose by a property the playable
    // character must have — a readable, plausible CurrentTransform.
    static uint32_t ids[8192];
    const int n = ListEntities(ids, 8192);

    uint32_t firstPlayer = 0;
    for (int i = 0; i < n; ++i) {
        if (ReadFaction(ids[i]) != faction::Player) continue;
        if (!firstPlayer) firstPlayer = ids[i];
        if (FindTransformSlot(ids[i]) < 0) continue;   // no usable position
        g_playerId.store(ids[i], std::memory_order_relaxed);
        WM_MOD_LOG("[wolfmount/entity] player entity = %u (faction Player, has "
                   "a readable position)", ids[i]);
        return ids[i];
    }

    if (firstPlayer) {
        // Fall back rather than returning 0: the entity is still the player,
        // and callers report "position unavailable" separately.
        g_playerId.store(firstPlayer, std::memory_order_relaxed);
        WM_MOD_LOG("[wolfmount/entity] player entity = %u (faction Player, but "
                   "no position slot was readable)", firstPlayer);
        return firstPlayer;
    }
    return 0;
}

namespace {

// Position slot is discovered by shape, not by name.
//
// Two encodings exist in this engine and the difference matters:
//   keen::ecs::CurrentTransform  (56 B) -> keen::WorldTransform, whose position
//                                          is three sint64 fixed-point values
//                                          in 1/2^32 metre units.
//   keen::ecs::Transform         (32 B) -> float3 position already in metres.
//
// We originally only looked for the 56-byte form because that is the one M182's
// Rust layer reads. The player template does carry CurrentTransform, but the
// component may be absent or unwritten on a live entity, so both shapes are
// accepted. Enshrouded's playable area is well under 100 km across, so
// |x|,|y|,|z| < 200000 metres is a very safe bound either way.
constexpr double kMaxPlausibleMeters = 200000.0;
constexpr uint16_t kTransformF32Size = 32;   // keen::ecs::Transform

bool PlausibleMeters(double x, double y, double z) {
    const double v[3] = {x, y, z};
    for (int k = 0; k < 3; ++k) {
        if (!std::isfinite(v[k]) || std::fabs(v[k]) > kMaxPlausibleMeters) {
            return false;
        }
    }
    return true;
}

// ---------------------------------------------------------------------------
//  Transform slot cache
//
//  The slot index for CurrentTransform depends only on the entity's *definition*
//  (the 640-slot table), never on the individual entity: two wolves share one
//  definition and one slot index. The search below costs one 0xf90-byte table
//  read plus a read per 56-byte candidate, which is far too much to repeat every
//  frame once a follower starts writing a position per tick.
//
//  So remember the answer per definition. A definition pointer is stable for the
//  life of the world, and if it is ever reused for different data the value
//  checks below reject the cached slot and the search runs again.
// ---------------------------------------------------------------------------
struct TransformSlotCache {
    uintptr_t def = 0;
    int slot = -1;
    uint16_t stride = 0;
    uint16_t offset = 0;   // slot's byte offset inside the entity chunk
    uint32_t uses = 0;
};

TransformSlotCache g_tsCache[8];
std::atomic<int> g_tsCacheNext{0};

TransformSlotCache* FindCache(uintptr_t def) {
    for (auto& c : g_tsCache) {
        if (c.def == def && c.slot >= 0) return &c;
    }
    return nullptr;
}

void StoreCache(uintptr_t def, int slot, uint16_t stride, uint16_t offset) {
    for (auto& c : g_tsCache) {
        if (c.def == def) {
            c.slot = slot;
            c.stride = stride;
            c.offset = offset;
            c.uses = 0;
            return;
        }
    }
    const int i = g_tsCacheNext.fetch_add(1) % 8;
    g_tsCache[i].def = def;
    g_tsCache[i].slot = slot;
    g_tsCache[i].stride = stride;
    g_tsCache[i].offset = offset;
    g_tsCache[i].uses = 0;
}

int FindTransformSlotImpl(uint32_t entityId, uint16_t* strideOut) {
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) {
        WM_MOD_LOG("[wolfmount/entity] transform lookup: entity %u is not live",
                   entityId);
        return -1;
    }
    const auto* def = reinterpret_cast<const uint8_t*>(ref.def);
    const uintptr_t defKey = reinterpret_cast<uintptr_t>(def);

    // Fast path: this definition was solved before, so we know the slot index,
    // stride and chunk offset and can address the component with no table read
    // at all. Confirm the cached slot still reads as a plausible position before
    // trusting it — a stale entry must fail loudly rather than make MoveEntity
    // write into a random component.
    if (TransformSlotCache* c = FindCache(defKey)) {
        const uintptr_t addr = ref.chunk + c->offset +
                               static_cast<size_t>(c->stride) * ref.slot;
        bool ok = false;
        if (addr) {
            if (c->stride == kTransformF32Size) {
                float f[3] = {0, 0, 0};
                ok = layout::Read(addr, f, sizeof(f)) &&
                     PlausibleMeters(f[0], f[1], f[2]) &&
                     !(f[0] == 0.0f && f[1] == 0.0f && f[2] == 0.0f);
            } else {
                int64_t v[3] = {0, 0, 0};
                ok = layout::Read(addr, v, sizeof(v)) &&
                     PlausibleMeters(layout::FixedToMeters(v[0]),
                                     layout::FixedToMeters(v[1]),
                                     layout::FixedToMeters(v[2])) &&
                     !(v[0] == 0 && v[1] == 0 && v[2] == 0);
            }
        }
        if (ok) {
            c->uses++;
            if (strideOut) *strideOut = c->stride;
            return c->slot;
        }
        WM_MOD_LOG("[wolfmount/entity] cached transform slot %d for def %p no "
                   "longer validates; re-deriving", c->slot,
                   reinterpret_cast<void*>(defKey));
        c->slot = -1;
    }

    // Read the definition tables once: SlotAddress() re-reads them per slot, and
    // this runs on the render thread.
    DefTables t;
    if (!t.Load(defKey)) return -1;

    int seen56 = 0;
    int seen32 = 0;
    int first32 = -1;
    for (int slot = 0; slot < layout::kComponentSlots; ++slot) {
        if (!t.Has(slot)) continue;
        const uint16_t stride = t.Stride(slot);

        if (stride == kTransformF32Size) {
            ++seen32;
            // A 32-byte component is NOT automatically a position: the
            // definition table only tells us the width. Read it and require the
            // three floats to look like a real world position, otherwise any
            // unrelated 32-byte component would be reported as "readable
            // position" and PlayerEntityId() would trust the wrong entity.
            if (first32 < 0) {
                const uintptr_t a32 = ref.chunk + t.Offset(slot) +
                                      static_cast<size_t>(kTransformF32Size) *
                                          ref.slot;
                float f[3] = {0, 0, 0};
                if (layout::Read(a32, f, sizeof(f)) &&
                    PlausibleMeters(f[0], f[1], f[2]) &&
                    !(f[0] == 0.0f && f[1] == 0.0f && f[2] == 0.0f)) {
                    first32 = slot;
                }
            }
        }
        if (stride != kTransformSize) continue;
        ++seen56;
        const uintptr_t addr = ref.chunk + t.Offset(slot) +
                               static_cast<size_t>(kTransformSize) * ref.slot;
        int64_t pos[3] = {0, 0, 0};
        if (!layout::Read(addr, pos, sizeof(pos))) continue;
        if (!PlausibleMeters(layout::FixedToMeters(pos[0]),
                             layout::FixedToMeters(pos[1]),
                             layout::FixedToMeters(pos[2]))) {
            continue;
        }
        if (pos[0] == 0 && pos[1] == 0 && pos[2] == 0) continue;
        if (strideOut) *strideOut = kTransformSize;
        StoreCache(defKey, slot, kTransformSize, t.Offset(slot));
        return slot;
    }

    // No usable fixed-point transform. Fall back to the 32-byte float form.
    if (first32 >= 0) {
        WM_MOD_LOG("[wolfmount/entity] entity %u: no fixed-point transform with "
                   "a live value (%d candidates, %d float transforms); using "
                   "slot %d (float3 position)", entityId, seen56, seen32, first32);
        if (strideOut) *strideOut = kTransformF32Size;
        StoreCache(defKey, first32, kTransformF32Size, t.Offset(first32));
        return first32;
    }

    WM_MOD_LOG("[wolfmount/entity] transform slot NOT found for entity %u "
               "(%d slots are 56 bytes wide, %d are 32 bytes)", entityId,
               seen56, seen32);
    return -1;
}

} // namespace

int FindTransformSlotEx(uint32_t entityId, uint16_t* strideOut) {
    return FindTransformSlotImpl(entityId, strideOut);
}

namespace {

int FindTransformSlot(uint32_t entityId) {
    return FindTransformSlotImpl(entityId, nullptr);
}

} // namespace

bool PlayerPosition(double* x, double* y, double* z) {
    const uint32_t pid = PlayerEntityId();
    if (!pid) return false;
    uint16_t stride = 0;
    const int slot = FindTransformSlotEx(pid, &stride);
    if (slot < 0) return false;
    mgr::EntityRef ref;
    if (!Lookup(pid, &ref)) {
        WM_MOD_LOG("[wolfmount/pos] player entity %u vanished from the manager "
                   "between the two lookups", pid);
        return false;
    }
    const uintptr_t addr = mgr::SlotAddressOf(ref, slot);
    if (!addr) {
        WM_MOD_LOG("[wolfmount/pos] player entity %u slot %d has no address",
                   pid, slot);
        return false;
    }

    double p[3] = {0, 0, 0};
    if (stride == kTransformF32Size) {
        float f[3] = {0, 0, 0};
        if (!layout::Read(addr, f, sizeof(f))) return false;
        p[0] = f[0]; p[1] = f[1]; p[2] = f[2];
    } else {
        int64_t v[3] = {0, 0, 0};
        if (!layout::Read(addr, v, sizeof(v))) return false;
        p[0] = layout::FixedToMeters(v[0]);
        p[1] = layout::FixedToMeters(v[1]);
        p[2] = layout::FixedToMeters(v[2]);
    }
    if (!PlausibleMeters(p[0], p[1], p[2])) {
        WM_MOD_LOG("[wolfmount/pos] player entity %u slot %d read %.3f %.3f "
                   "%.3f m — outside the plausible range", pid, slot, p[0], p[1],
                   p[2]);
        return false;
    }
    if (x) *x = p[0];
    if (y) *y = p[1];
    if (z) *z = p[2];
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

bool LogEntitySnapshot() {
    const int slot = FactionSlot();
    if (slot < 0) return false;
    if (!HasManager()) return false;

    static uint32_t ids[8192];
    const int n = ListEntities(ids, 8192);
    if (n <= 0) {
        WM_MOD_LOG("[wolfmount/snapshot] deferred: entity table empty");
        return false;
    }

    // Tally factions over the whole live population. This is the single most
    // useful fact about a session: it says whether the discovered slot is
    // really Faction, and whether the world actually contains a Player and any
    // WildBeast at this moment.
    int counts[16] = {0};
    int outOfRange = 0;
    int unreadable = 0;
    for (int i = 0; i < n; ++i) {
        mgr::EntityRef ref;
        if (!Lookup(ids[i], &ref)) continue;
        uint8_t v = 0xFF;
        if (!mgr::ReadSlot(ref, slot, &v, 1)) { ++unreadable; continue; }
        if (v < 16) ++counts[v];
        else ++outOfRange;
    }

    char tally[256] = {0};
    for (int f = 0; f < 16; ++f) {
        if (!counts[f]) continue;
        char one[40];
        snprintf(one, sizeof(one), "%s%s=%d", tally[0] ? " " : "",
                 game::FactionName((uint8_t)f), counts[f]);
        strncat(tally, one, sizeof(tally) - strlen(tally) - 1);
    }

    const uint32_t player = PlayerEntityId();
    double px = 0, py = 0, pz = 0;
    const bool havePos = PlayerPosition(&px, &py, &pz);

    WM_MOD_LOG("[wolfmount/snapshot] %d entities, faction slot %d: %s "
               "(out-of-range %d, unreadable %d)",
               n, slot, tally[0] ? tally : "(none)", outOfRange, unreadable);
    if (player) {
        WM_MOD_LOG("[wolfmount/snapshot] player=%u position=%.1f,%.1f,%.1f%s",
                   player, px, py, pz, havePos ? "" : " (unavailable)");
    } else {
        WM_MOD_LOG("[wolfmount/snapshot] player NOT visible through this slot");
    }
    WM_MOD_LOG("[wolfmount/snapshot] wild beasts visible: %d", counts[6]);

    // Only claim readiness when the slot demonstrably reads both factions that
    // make it Faction. Anything else means the discovery picked the wrong byte
    // and writing through it would corrupt an unrelated component.
    const bool usable = (counts[faction::Player] > 0) && (outOfRange == 0);
    WM_MOD_LOG("[wolfmount/snapshot] faction slot usable for writes: %s",
               usable ? "yes" : "NO (player not found through it)");
    return usable;
}

bool ReadComponent(uint32_t entityId, int slot, void* buf, uint16_t stride) {    mgr::EntityRef ref;
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

    uint32_t levelValue = level;

    // Component descriptor array: 24 bytes per entry.
    //   +0x00 u32 hash
    //   +0x08 void* data
    //   +0x10 u64 size
    //
    // NOTE: the factory at RVA 0x97B790 NEVER READS desc+0x18, so this array is
    // not consumed by the game. It is kept only because M182's own calibration
    // reads it back after Create returns to work out which slot the template's
    // transform landed in (spawner.rs:1074-1082). See the comment in
    // entityops.h before trusting anything about positioning here.
    // A zeroed placeholder is enough for that purpose: the calibration only
    // needs the array to exist at a known address, and the game never reads it.
    alignas(16) uint8_t entries[0x40] = {0};
    const uint32_t nEntries = 2;
    memcpy(entries + 0,  &kHashCurrentTransform, 4);
    uint64_t p = reinterpret_cast<uint64_t>(entries);
    memcpy(entries + 8,  &p, 8);
    uint64_t sz = kTransformSize;
    memcpy(entries + 16, &sz, 8);
    memcpy(entries + 24, &kHashOverrideLevel, 4);
    p = reinterpret_cast<uint64_t>(&levelValue);
    memcpy(entries + 32, &p, 8);
    sz = 4;
    memcpy(entries + 40, &sz, 8);

    // Spawn descriptor. The factory reads exactly two fields of this struct:
    //   +0x04  16-byte template GUID   (movups 0x4(%r8),%xmm0 at rva 0x97B8A9)
    //   +0x20  component count         (leaq  0x20(%r8),%rax at rva 0x97B7BB)
    // desc+0x18 is never read anywhere in the 0x97B790..0x97D358 span.
    alignas(16) uint8_t desc[0x40] = {0};
    memcpy(desc + 4, guid, 16);
    p = reinterpret_cast<uint64_t>(entries);
    memcpy(desc + 0x18, &p, 8);
    uint64_t count = nEntries;
    memcpy(desc + 0x20, &count, 8);

    const uint32_t id = create(reinterpret_cast<void*>(m), 0, desc, nullptr);
    if (id == 0) {
        WM_MOD_LOG("[wolfmount/spawn] create(guid %02x%02x%02x%02x...) -> "
                   "no entity", guid[0], guid[1], guid[2], guid[3]);
        return 0;
    }

    // The factory positions the entity wherever the template says, ignoring
    // every coordinate we passed. Move it explicitly, and say so.
    const bool moved = MoveEntity(id, x, y, z);
    WM_MOD_LOG("[wolfmount/spawn] create(guid %02x%02x%02x%02x...) -> entity %u;"
               " factory ignores position, MoveEntity(%.1f, %.1f, %.1f) = %s",
               guid[0], guid[1], guid[2], guid[3], id, x, y, z,
               moved ? "ok" : "FAILED (see transform slot note)");
    return id;
}

bool MoveEntity(uint32_t entityId, double x, double y, double z) {
    if (!entityId) return false;
    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) {
        // A freshly spawned entity may not be registered in the hash table on
        // the same frame it is returned. Say that plainly instead of guessing.
        WM_MOD_LOG("[wolfmount/move] entity %u not yet in the manager; "
                   "position left at the template default", entityId);
        return false;
    }
    uint16_t stride = 0;
    const int slot = FindTransformSlotEx(entityId, &stride);
    if (slot < 0) {
        WM_MOD_LOG("[wolfmount/move] entity %u: no plausible position slot "
                   "found, refusing to guess", entityId);
        return false;
    }
    const uintptr_t addr = mgr::SlotAddressOf(ref, slot);
    if (!addr) return false;

    // Write in whichever encoding this slot actually uses. Encoding a float
    // transform as fixed-point (or the reverse) would corrupt the component,
    // so the choice is driven by the stride that was found, not by a constant.
    if (stride == kTransformF32Size) {
        float f[3] = {(float)x, (float)y, (float)z};
        if (!layout::Write(addr, f, sizeof(f))) {
            WM_MOD_LOG("[wolfmount/move] entity %u slot %d not writable",
                       entityId, slot);
            return false;
        }
        float back[3] = {0, 0, 0};
        if (!layout::Read(addr, back, sizeof(back)) ||
            memcmp(back, f, sizeof(f))) {
            WM_MOD_LOG("[wolfmount/move] entity %u slot %d read-back mismatch",
                       entityId, slot);
            return false;
        }
    } else {
        int64_t pos[3] = {layout::MetersToFixed(x), layout::MetersToFixed(y),
                          layout::MetersToFixed(z)};
        if (!layout::Write(addr, pos, sizeof(pos))) {
            WM_MOD_LOG("[wolfmount/move] entity %u slot %d not writable",
                       entityId, slot);
            return false;
        }
        // Read back: a position write that did not stick is not a success.
        int64_t back[3] = {0, 0, 0};
        if (!layout::Read(addr, back, sizeof(back)) ||
            memcmp(back, pos, sizeof(pos))) {
            WM_MOD_LOG("[wolfmount/move] entity %u slot %d read-back mismatch",
                       entityId, slot);
            return false;
        }
    }
    WM_MOD_LOG("[wolfmount/move] entity %u -> (%.1f, %.1f, %.1f) via slot %d "
               "(%s)", entityId, x, y, z, slot,
               stride == kTransformF32Size ? "float3" : "fixed-point");
    return true;
}

int SpawnNearPlayer(const uint8_t guid[16], int count, double distance,
                    uint32_t level) {
    double x = 0, y = 0, z = 0;
    bool havePos = PlayerPosition(&x, &y, &z);
    if (!havePos) {
        // Do NOT refuse. The factory ignores the position we pass anyway (it
        // reads only desc+0x04 and desc+0x20; see docs/TECHNIQUE.md §5a), so a
        // missing player transform cannot prevent a spawn — it only means we
        // cannot pick WHERE. Falling through lets us prove the Create chain on
        // its own, which is the harder half of this feature.
        WM_MOD_LOG("[wolfmount/spawn] no player position; spawning at the "
                   "template's own location (position is applied afterwards)");
    }
    if (count < 1) count = 1;
    if (count > 8) count = 8;
    if (distance < 0.5) distance = 0.5;

    int spawned = 0;
    for (int i = 0; i < count; ++i) {
        const double angle = 2.0 * 3.14159265358979323846 * i / count;
        const double sx = havePos ? x + distance * std::cos(angle) : 0.0;
        const double sz = havePos ? z + distance * std::sin(angle) : 0.0;
        const uint32_t id = SpawnAt(guid, sx, havePos ? y + 0.5 : 0.0, sz, level);
        if (id == 0) {
            WM_MOD_LOG("[wolfmount/spawn] attempt %d/%d: factory returned 0",
                       i + 1, count);
            continue;
        }
        // Verify the entity is actually in the manager; the factory returning a
        // non-zero id is not the same as a live entity.
        mgr::EntityRef ref;
        const bool live = Lookup(id, &ref);
        WM_MOD_LOG("[wolfmount/spawn] attempt %d/%d: id=%u live=%d", i + 1,
                   count, id, live ? 1 : 0);
        if (live) ++spawned;
    }
    WM_MOD_LOG("[wolfmount/spawn] requested %d, verified live %d", count,
               spawned);
    return spawned;
}

// Spawn and immediately enrol the result as a follower. Kept separate from
// SpawnNearPlayer so a spawn used for a test target does not start trailing the
// player by accident.
int SpawnFollower(const uint8_t guid[16], int count, double distance,
                  uint32_t level) {
    double x = 0, y = 0, z = 0;
    const bool havePos = PlayerPosition(&x, &y, &z);
    int spawned = 0;
    for (int i = 0; i < count; ++i) {
        const double angle = 2.0 * 3.14159265358979323846 * i / count;
        const double sx = havePos ? x + distance * std::cos(angle) : 0.0;
        const double sz = havePos ? z + distance * std::sin(angle) : 0.0;
        const uint32_t id = SpawnAt(guid, sx, havePos ? y + 0.5 : 0.0, sz, level);
        if (id == 0) {
            WM_MOD_LOG("[wolfmount/spawn] follower attempt %d/%d: factory "
                       "returned 0", i + 1, count);
            continue;
        }
        mgr::EntityRef ref;
        if (!Lookup(id, &ref)) {
            WM_MOD_LOG("[wolfmount/spawn] follower attempt %d/%d: id=%u is not "
                       "in the manager, not enrolling it", i + 1, count, id);
            continue;
        }
        ++spawned;
        // A fresh wolf is WildBeast: it would bite the player, and its own AI
        // would treat the player as prey. Faction is the byte the AI actually
        // reads, and the spawn descriptor cannot set it (the factory reads only
        // the template GUID and the component count -- docs/TECHNIQUE.md §5a),
        // so write it now. PlayerAlly gives both halves of "fights for me":
        // the player-group rule stops it attacking us, and IsEnemy's default
        // branch makes it attack every other faction.
        if (FactionSlot() >= 0) {
            if (!WriteFaction(id, faction::kPlayerAlly)) {
                WM_MOD_LOG("[wolfmount/spawn] entity %u: faction write FAILED; "
                           "it stays hostile", id);
            }
        } else {
            WM_MOD_LOG("[wolfmount/spawn] entity %u: faction slot not discovered "
                       "yet, so it is still WildBeast and will attack", id);
        }
        // Enrol it right away: a new companion standing at the template's
        // default position would otherwise wait for the first follow tick to be
        // brought over, which reads as "the summon did nothing".
        FollowAdd(id);
        const int f = ReadFaction(id);
        WM_MOD_LOG("[wolfmount/spawn] follower attempt %d/%d: id=%u live=1 "
                   "faction=%d", i + 1, count, id, f);
    }
    WM_MOD_LOG("[wolfmount/spawn] followers requested %d, verified live %d",
               count, spawned);
    return spawned;
}

// ---------------------------------------------------------------------------
//  Follow loop
// ---------------------------------------------------------------------------

namespace {

std::atomic<uint32_t> g_followTick{0};

} // namespace

bool FollowAdd(uint32_t entityId) {
    const bool ok = followset::Add(entityId);
    if (!ok && entityId) {
        WM_MOD_LOG("[wolfmount/follow] set full (%d); not adding entity %u",
                   followset::kMaxFollowers, entityId);
    } else if (ok) {
        WM_MOD_LOG("[wolfmount/follow] entity %u now follows (%d in set)",
                   entityId, followset::Count());
    }
    // Remembered even when the set is full, and kept after a removal: the mount
    // button has to offer *something* to ride, and a wolf that just died is
    // still the one the player was standing next to.
    if (entityId) g_lastFollower.store(entityId, std::memory_order_relaxed);
    return ok;
}

void FollowRemove(uint32_t entityId) {
    const int before = followset::Count();
    followset::Remove(entityId);
    if (followset::Count() != before) {
        WM_MOD_LOG("[wolfmount/follow] entity %u no longer follows (%d left)",
                   entityId, followset::Count());
    }
}

void FollowClear() {
    followset::Clear();
    WM_MOD_LOG("[wolfmount/follow] follow set cleared");
}

int FollowCount() { return followset::Count(); }

int FollowTick(double behindMetres, double teleportBeyond) {
    const int n = followset::Count();
    if (n == 0) return 0;

    // This runs from the render thread every frame, so it must not probe the
    // manager or scan for the player unless those answers are already cheap.
    // Both are cached by their own code paths, but a world without a manager
    // should cost nothing at all.
    if (!HasManager()) return 0;

    double px = 0, py = 0, pz = 0;
    if (!PlayerPosition(&px, &py, &pz)) return 0;

    // Stagger: moving every follower on every frame is pointless (the AI cannot
    // use sub-frame precision) and multiplies the log noise. One follower per
    // tick round-robins through the set, so a set of N is refreshed every N
    // frames and a set of one is refreshed every frame.
    const uint32_t tick = g_followTick.fetch_add(1, std::memory_order_relaxed);
    const int who = static_cast<int>(tick % static_cast<uint32_t>(n));

    const uint32_t id = followset::At(who);
    if (!id) return 0;

    mgr::EntityRef ref;
    if (!Lookup(id, &ref)) {
        // The companion is gone (killed, or unloaded with its cell). Drop it so
        // the set does not slowly fill with ghosts.
        WM_MOD_LOG("[wolfmount/follow] entity %u is no longer live; dropping it",
                   id);
        FollowRemove(id);
        return 0;
    }

    // Aim slightly behind the player rather than on top of them: a follower that
    // targets the player's own position jitters and shoves the player around.
    const double tx = px - behindMetres;
    const double ty = py;
    const double tz = pz - behindMetres;

    // Read where it is now, so a far-away follower is teleported rather than
    // asked to walk across the map.
    uint16_t stride = 0;
    const int slot = FindTransformSlotEx(id, &stride);
    if (slot < 0) return 0;

    const uintptr_t addr = mgr::SlotAddressOf(ref, slot);
    if (!addr) return 0;

    double cx = 0, cy = 0, cz = 0;
    if (stride == kTransformF32Size) {
        float f[3] = {0, 0, 0};
        if (!layout::Read(addr, f, sizeof(f))) return 0;
        cx = f[0]; cy = f[1]; cz = f[2];
    } else {
        int64_t v[3] = {0, 0, 0};
        if (!layout::Read(addr, v, sizeof(v))) return 0;
        cx = layout::FixedToMeters(v[0]);
        cy = layout::FixedToMeters(v[1]);
        cz = layout::FixedToMeters(v[2]);
    }

    const double dx = tx - cx;
    const double dz = tz - cz;
    const double dist = std::sqrt(dx * dx + dz * dz);

    // Already close enough: leave it alone so its own AI keeps running. This is
    // the important half of the design -- the wolf's combat behaviour lives in
    // the engine, and continuously rewriting its position would fight it.
    if (dist < behindMetres * 2.0) return 0;

    if (dist > teleportBeyond) {
        if (MoveEntity(id, tx, ty, tz)) {
            WM_MOD_LOG("[wolfmount/follow] entity %u teleported to the player "
                       "(was %.0f m away)", id, dist);
            return 1;
        }
        return 0;
    }

    // Walk it part of the way. A fraction per tick keeps the motion smooth and
    // stops the follower from overshooting when the player is moving.
    const double step = dist < 8.0 ? dist : 8.0;
    const double nx = cx + dx / dist * step;
    const double nz = cz + dz / dist * step;
    if (MoveEntity(id, nx, cy, nz)) {
        WM_MOD_LOG("[wolfmount/follow] entity %u stepped %.1f m toward the "
                   "player (%.1f m to go)", id, step, dist - step);
        return 1;
    }
    return 0;
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

// One-shot position diagnosis. Called from the console so a single session
// answers every question about why the player's coordinates cannot be read:
// which entities claim Faction == Player, and for each 56-byte component on
// them, the raw int64 triple and what it converts to in metres.
void DumpPlayerPosition() {
    const int slot = FactionSlot();
    WM_MOD_LOG("[wolfmount/pos] faction slot = %d", slot);
    if (slot < 0) {
        WM_MOD_LOG("[wolfmount/pos] cannot search: faction slot unknown");
        return;
    }

    static uint32_t ids[8192];
    const int n = ListEntities(ids, 8192);
    WM_MOD_LOG("[wolfmount/pos] scanning %d live entities for Faction==Player",
               n);

    int players = 0;
    for (int i = 0; i < n && players < 4; ++i) {
        const int f = ReadFaction(ids[i]);
        if (f != faction::Player) continue;
        ++players;

        mgr::EntityRef ref;
        if (!Lookup(ids[i], &ref)) continue;
        DefTables t;
        if (!t.Load(ref.def)) {
            WM_MOD_LOG("[wolfmount/pos] entity %u: definition unreadable",
                       ids[i]);
            continue;
        }

        WM_MOD_LOG("[wolfmount/pos] entity %u (Faction Player) chunk=%p slot=%u",
                   ids[i], reinterpret_cast<void*>(ref.chunk), ref.slot);

        int shown = 0;
        for (int s = 0; s < layout::kComponentSlots && shown < 8; ++s) {
            if (!t.Has(s)) continue;
            if (t.Stride(s) != kTransformSize) continue;
            const uintptr_t addr = ref.chunk + t.Offset(s) +
                                   static_cast<size_t>(kTransformSize) * ref.slot;
            int64_t v[3] = {0, 0, 0};
            if (!layout::Read(addr, v, sizeof(v))) {
                WM_MOD_LOG("[wolfmount/pos]   slot %3d stride 56 addr %p  "
                           "UNREADABLE", s, reinterpret_cast<void*>(addr));
                ++shown;
                continue;
            }
            WM_MOD_LOG("[wolfmount/pos]   slot %3d stride 56 addr %p  "
                       "raw %lld %lld %lld  = %.3f %.3f %.3f m",
                       s, reinterpret_cast<void*>(addr),
                       (long long)v[0], (long long)v[1], (long long)v[2],
                       layout::FixedToMeters(v[0]),
                       layout::FixedToMeters(v[1]),
                       layout::FixedToMeters(v[2]));
            ++shown;
        }
        if (!shown) {
            WM_MOD_LOG("[wolfmount/pos]   no 56-byte component at all");
        }
    }

    if (!players) {
        WM_MOD_LOG("[wolfmount/pos] no entity currently reads Faction == Player");
    }
}

// ---------------------------------------------------------------------------
//  Riding
//
//  The engine has no mount to enter (see the comment block in entityops.h), so
//  riding is reduced to the part that is both visible and safe: while mounted,
//  the player's transform is written from the wolf's transform plus the anchor
//  offset. The wolf keeps its own movement and combat AI; the player inherits
//  it, which is exactly the physical relationship "riding" describes.
//
//  Deliberately NOT attempted here:
//    - the camera stays the player's own (there is no reachable state machine
//      to move it, see mount.cpp's plan);
//    - the seated pose is not applied;
//    - no speed or control change is made to the wolf.
//  Anything beyond copying the transform would need the program dispatcher,
//  and calling a handler directly has already been shown to fault (the
//  transformer crash at RVA 0x9B8013).
// ---------------------------------------------------------------------------

namespace {

std::atomic<uint32_t> g_mountedId{0};
std::atomic<int>      g_mountTicks{0};
std::atomic<int>      g_mountWrites{0};

// The anchor: one metre straight up from the wolf's origin, matching the
// "Root" attachment slot the wolf itself ships for the hookshot. Reusing the
// shipped anchor rather than inventing an offset means the rider stands where
// the game already expects a body to be able to sit.
constexpr double kMountHeightMetres = 1.0;

} // anonymous namespace

uint32_t MountedEntity() {
    return g_mountedId.load(std::memory_order_relaxed);
}

bool IsMounted() {
    return g_mountedId.load(std::memory_order_relaxed) != 0;
}

uint32_t FollowAt(int index) {
    return followset::At(index);
}

uint32_t LastFollower() {
    return g_lastFollower.load(std::memory_order_relaxed);
}

bool MountOnto(uint32_t entityId) {
    if (entityId == 0) {
        WM_MOD_LOG("[wolfmount/mount] refused: entity id 0");
        return false;
    }
    if (IsMounted()) {
        WM_MOD_LOG("[wolfmount/mount] already mounted on %u",
                   g_mountedId.load(std::memory_order_relaxed));
        return false;
    }
    if (!HasManager()) {
        WM_MOD_LOG("[wolfmount/mount] refused: no entity manager (no world?)");
        return false;
    }

    mgr::EntityRef ref;
    if (!Lookup(entityId, &ref)) {
        WM_MOD_LOG("[wolfmount/mount] refused: entity %u is not live", entityId);
        return false;
    }

    // A mount has to be something we can actually follow: no transform slot
    // means we cannot keep the player on it, and the rider would be left
    // standing wherever they were while the wolf walks away.
    uint16_t stride = 0;
    const int slot = FindTransformSlotEx(entityId, &stride);
    if (slot < 0) {
        WM_MOD_LOG("[wolfmount/mount] refused: entity %u has no readable "
                   "transform slot", entityId);
        return false;
    }

    const uint32_t player = PlayerEntityId();
    if (player == 0) {
        WM_MOD_LOG("[wolfmount/mount] refused: player entity not identified");
        return false;
    }

    uint16_t pstride = 0;
    if (FindTransformSlotEx(player, &pstride) < 0) {
        WM_MOD_LOG("[wolfmount/mount] refused: player %u has no readable "
                   "transform slot", player);
        return false;
    }

    g_mountedId.store(entityId, std::memory_order_relaxed);
    g_mountTicks.fetch_add(1, std::memory_order_relaxed);

    // A mounted wolf is driven by its rider, not by the trail-behind rule:
    // the follow loop would otherwise drag the player along behind it.
    FollowRemove(entityId);

    WM_MOD_LOG("[wolfmount/mount] mounted on entity %u (slot %d, stride %u); "
               "player %u will inherit its transform",
               entityId, slot, stride, player);
    return true;
}

bool Dismount() {
    const uint32_t id = g_mountedId.exchange(0, std::memory_order_relaxed);
    if (id == 0) {
        WM_MOD_LOG("[wolfmount/mount] not mounted");
        return false;
    }
    WM_MOD_LOG("[wolfmount/mount] dismounted from entity %u", id);
    return true;
}

int MountTick() {
    const uint32_t id = g_mountedId.load(std::memory_order_relaxed);
    if (id == 0) return 0;
    if (!HasManager()) return 0;

    g_mountTicks.fetch_add(1, std::memory_order_relaxed);

    // The wolf may have died or been unloaded with its cell while we sat on it.
    // Dropping the mount here is the only safe response: there is nothing left
    // to copy, and staying "mounted" would freeze the player in place.
    mgr::EntityRef ref;
    if (!Lookup(id, &ref)) {
        WM_MOD_LOG("[wolfmount/mount] entity %u is no longer live; dropping "
                   "the mount", id);
        g_mountedId.store(0, std::memory_order_relaxed);
        return 0;
    }

    uint16_t stride = 0;
    const int slot = FindTransformSlotEx(id, &stride);
    if (slot < 0) {
        WM_MOD_LOG("[wolfmount/mount] entity %u lost its transform slot; "
                   "dropping the mount", id);
        g_mountedId.store(0, std::memory_order_relaxed);
        return 0;
    }

    const uintptr_t addr = mgr::SlotAddressOf(ref, slot);
    if (!addr) return 0;

    double wx = 0, wy = 0, wz = 0;
    if (stride == kTransformF32Size) {
        float f[3] = {0, 0, 0};
        if (!layout::Read(addr, f, sizeof(f))) return 0;
        wx = f[0]; wy = f[1]; wz = f[2];
    } else {
        int64_t v[3] = {0, 0, 0};
        if (!layout::Read(addr, v, sizeof(v))) return 0;
        wx = layout::FixedToMeters(v[0]);
        wy = layout::FixedToMeters(v[1]);
        wz = layout::FixedToMeters(v[2]);
    }

    // Sit on the back, not inside the wolf's origin.
    if (!MoveEntity(PlayerEntityId(), wx, wy + kMountHeightMetres, wz)) {
        return 0;
    }

    g_mountWrites.fetch_add(1, std::memory_order_relaxed);
    return 1;
}

} // namespace wolfmount::entityops
