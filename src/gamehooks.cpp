// ============================================================================
//  WolfMount — game hooks (M3/M6)
//
//  Wires the taming decision (tame.cpp) into the real game event system.
//
//  WHAT WE HOOK AND WHY
//  -------------------
//  `EntityDiedEvent` is unusable for the torch rule: it carries only
//  `deadEntityId` (size 16, one field) — no weapon, no attacker.
//
//  `HitEvent` (size 248, hash 0xCC0D57E0) carries everything we need.
//  Offsets live in gamehooks.h namespace `hit` and come straight out of the
//  binary's reflection table (`keen::ecs::HitEvent`, index 3298).
//
//  We hook the ENTRY of `SendEvent` (0x140955400), the single generic event
//  writer that all 126 call sites funnel through:
//
//      void* SendEvent(void* buf, u32 typeHash, u32 size, u32 entityId)
//
//  Hooking the entry rather than a call site matters: replacing a `call` with
//  a `jmp` loses the pushed return address and misaligns rsp by 8 bytes, which
//  crashed the game inside ucrtbase's aligned `movdqa`. At the entry the hook
//  is an ordinary function and the ABI stays intact.
//
//  DEFERRED READ — the reason the first version logged all zeros:
//  SendEvent zeroes the payload before returning (xor edx,edx -> call memset ->
//  lea rax,[rbx+8]), and callers fill the fields in *afterwards*. So reading on
//  entry always sees zeros. We therefore flush the *previous* pending record at
//  the start of each call — by then its caller has finished writing it.
//
//  READ-ONLY in this milestone: the hook observes hits and logs the ids. That
//  mapping is what the write path needs next.
// ============================================================================

#include "gamehooks.h"
#include "detour.h"
#include "gamedata.h"
#include "logging.h"
#include "reflect.h"

#include <windows.h>

#include <atomic>
#include <cstdio>
#include <cstring>
#include <cstdint>

namespace wolfmount::gamehooks {

namespace {

detour::Hook g_hookHit;
std::atomic<bool> g_active{false};
HMODULE g_gameModule = nullptr;

uintptr_t GameBase() {
    if (!g_gameModule) {
        g_gameModule = GetModuleHandleA("enshrouded.exe");
        if (!g_gameModule) g_gameModule = GetModuleHandleA("enshrouded_server.exe");
    }
    return reinterpret_cast<uintptr_t>(g_gameModule);
}

// Counter so the log does not grow unbounded during a long session.
std::atomic<int> g_hitCount{0};
constexpr int kMaxLoggedHits = 500;

// ---------------------------------------------------------------------------
//  Detour body
//
//  We hook the *entry* of SendEvent (0x140955400), NOT one of its call sites.
//
//  Why the entry matters: replacing a `call` instruction with this engine's
//  absolute `jmp` would suppress the pushed return address, so our detour
//  would enter with rsp 16-aligned instead of the ABI's 8-mod-16, and its
//  `ret` would pop garbage. That misalignment made ucrtbase's `movdqa`
//  fault (0xC0000005 at ucrtbase+0x352C7) on the first HitEvent.
//
//  Hooking the entry keeps the caller's return address intact, so this is an
//  ordinary function with an ordinary calling convention:
//      rcx = event buffer
//      edx = type hash
//      r8d = size
//      r9d = entity id
//  and the return value is the payload pointer (record + 8).
//
//  DEFERRED READ — this is the subtle part.
//  SendEvent zeroes the whole payload before returning:
//        14095544d  xor edx,edx
//        14095545a  lea rcx,[rbx+8]
//        140955461  call memset
//        140955466  lea rax,[rbx+8]   ; return
//  The *caller* then fills the fields one by one (NoiseEvent writes +8, +0x8C,
//  +0x94 after the call). So reading the record inside the hook sees zeros.
//  We therefore keep the previous record pending and flush it on the NEXT
//  SendEvent, by which time the caller has written every field.
// ---------------------------------------------------------------------------
using SendEventFn = void* (*)(void*, uint32_t, uint32_t, uint32_t);

SendEventFn g_origSend = nullptr;

// The trampoline replays SendEvent's stolen prologue then jumps back into the
// real body, so this pointer is what actually performs the write.
SendEventFn g_trampoline = nullptr;

// Pending HitEvent payload from the previous SendEvent call, read one event
// later (see DEFERRED READ above).
const uint8_t* g_pendingHit = nullptr;
std::atomic<int> g_pendingCount{0};

// Defined with the write path further down; used when a hit is flushed.
void RememberFaction(uint32_t eid, uint8_t faction);

// Most recent entity seen as the victim of a HitEvent with faction WildBeast
// (6) — i.e. a live wild wolf.
std::atomic<uint32_t> g_lastWildBeast{0};

// Torch-kill taming: on by default, can be switched off from the menu.
std::atomic<bool> g_torchTame{true};
std::atomic<int>  g_torchTameCount{0};

// Move a torch-tamed wolf to Faction 11 (PlayerAlly) so it fights for us.
std::atomic<bool> g_allyOnTame{true};
std::atomic<int>  g_factionIssued{0};

// Armed by the torch rule in FlushPendingHit(), consumed by DetourEnqueue().
// Declared here because the hit reader is defined above the Enqueue plumbing.
extern std::atomic<uint32_t> g_pendingTameEid;

void FlushPendingHit() {
    const uint8_t* p = g_pendingHit;
    if (!p) return;
    g_pendingHit = nullptr;

    if (IsBadReadPtr(p, rva::HitEventSize)) return;

    // The event ring can be drained and refilled between our two hook calls, so
    // a stashed payload may no longer belong to the HitEvent we saw. Verify the
    // record header that precedes the payload (SendEvent returns record+8):
    //   record+0 = type hash, record+6 = size byte.
    // If either is wrong, the slot was recycled — refuse to report a hit we
    // cannot prove.
    uint32_t hdrHash = 0;
    uint8_t  hdrSize = 0;
    memcpy(&hdrHash, p - 8, 4);
    memcpy(&hdrSize, p - 2, 1);
    if (hdrHash != rva::HitEventHash || hdrSize != (uint8_t)rva::HitEventSize) {
        return;
    }

    uint32_t rootTargetId = 0, sourceId = 0, weaponPideId = 0;
    int32_t  healthChange = 0;
    uint32_t weaponCategory = 0;
    uint8_t  targetFaction = 0xFF;
    uint16_t hitReaction = 0;
    uint16_t impactId = 0;
    uint16_t damageTypes = 0;

    memcpy(&rootTargetId,   p + hit::RootTargetId,   4);
    memcpy(&sourceId,       p + hit::SourceId,       4);
    memcpy(&weaponPideId,   p + hit::WeaponPideId,   4);
    memcpy(&healthChange,   p + hit::HealthChange,   4);
    memcpy(&weaponCategory, p + hit::WeaponCategory, 4);
    memcpy(&targetFaction,  p + hit::TargetFaction,  1);
    memcpy(&hitReaction,    p + hit::HitReaction,    2);
    memcpy(&impactId,       p + hit::ImpactId,       2);
    memcpy(&damageTypes,    p + hit::DamageTypes,    2);

    // The event buffer is a ring the game drains and refills between our two
    // hook calls, so a stashed record can already have been recycled by the
    // time we read it. Entity ids are small (u16 in the record header), so
    // anything outside that range is a recycled record, not a real hit — drop
    // it rather than reporting a wolf id that does not exist.
    if (rootTargetId == 0 || rootTargetId > 0xFFFF ||
        sourceId > 0xFFFF || targetFaction > 15) {
        return;
    }

    int n = g_hitCount.fetch_add(1) + 1;
    if (n <= kMaxLoggedHits) {
        WM_MOD_LOG("[wolfmount] HIT #%d target=%u source=%u weapon=%u dmg=%d "
                   "cat=%u faction=%u(%s) reaction=%u impact=%u dmgtypes=0x%04X",
                   n, rootTargetId, sourceId, weaponPideId, healthChange,
                   weaponCategory, (unsigned)targetFaction,
                   game::FactionName(targetFaction), (unsigned)hitReaction,
                   (unsigned)impactId, (unsigned)damageTypes);
    }

    // Remember the victim's faction: that is how the menu tells a wild wolf
    // (FactionType 6 = WildBeast) from a farm animal.
    RememberFaction(rootTargetId, targetFaction);

    // Also remember the most recent wild beast we have SEEN, so the menu can
    // offer "tame that wolf" without the player having to type an entity id.
    if (targetFaction == game::kFactionWildBeast && rootTargetId != 0) {
        g_lastWildBeast.store(rootTargetId, std::memory_order_relaxed);
    }

    // ---- torch rule ------------------------------------------------------
    // A torch does fire damage: DamageTypeNew::Magical_Fire == 3, so bit 3 of
    // the DamageTypeMask is set. Weapons such as swords set Physical_Cut
    // instead, which is what separates a torch kill from an ordinary one.
    const bool isFire = (damageTypes & (1u << 3)) != 0;
    if (g_torchTame.load(std::memory_order_relaxed) &&
        isFire &&
        targetFaction == game::kFactionWildBeast &&
        rootTargetId != 0) {
        // Arm it; the write itself happens on the game thread inside Enqueue,
        // where mutating the queue cannot race with the game's own writers.
        g_pendingTameEid.store(rootTargetId, std::memory_order_release);
        const int n2 = g_torchTameCount.fetch_add(1) + 1;
        WM_MOD_LOG("[wolfmount] TORCH tame armed for entity %u (fire hit, "
                   "faction WildBeast, dmg=%d) — total %d",
                   rootTargetId, healthChange, n2);
    }
}

void* DetourSendEvent(void* buffer, uint32_t value, uint32_t typeTag, size_t size) {
    // 1. Flush whatever the previous call produced — its fields are complete now.
    FlushPendingHit();

    // 2. Perform the real write.
    void* record = g_trampoline
        ? g_trampoline(buffer, value, typeTag, (uint32_t)size)
        : nullptr;

    // 3. Bounded trace. The body rejects typeTag >= 0x100, so this queue is a
    //    small-tag integer channel — not the FNV-hash event bus we once thought.
    //    Logging every call is the only way to learn what actually uses it.
    static std::atomic<int> s_sendCount{0};
    const int n = s_sendCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 60 || (n % 200) == 0) {
        WM_MOD_LOG("[wolfmount] SEND #%d buf=%p value=%u tag=%u size=%u -> %p",
                   n, buffer, value, (unsigned)typeTag, (unsigned)size, record);
    }
    if (record && typeTag < 0x100) {
        g_pendingHit = static_cast<const uint8_t*>(record) - 8;
    }

    return record;
}

// ---------------------------------------------------------------------------
//  Write path
//
//  `Enqueue` (0x952400) is the single funnel every component write goes
//  through, and its first argument is the world/entity admin — the `ctx` that
//  `SetIsTame` needs. Rather than pointer-chase for the world, we learn it from
//  the hook: the first component the game writes hands it to us.
//
//  Signature (recovered from SetIsTame's own call into it):
//      void* Enqueue(void* ctx, void* buf, uint8_t flags,
//                    uint32_t size, uint32_t entityId)
//  The 5th argument is stack-passed, which is why this detour is declared with
//  five parameters: the caller's `call` still pushes its return address, so the
//  stack layout our prologue sees is exactly the callee's.
//
//  IMPORTANT: the tame write is issued from INSIDE this detour, i.e. on the game
//  thread, not from the render/menu thread. `Enqueue` mutates the queue's
//  writeIndex in `ctx+0x10`; doing that concurrently with the game would corrupt
//  it. Issuing the write where the game itself issues writes removes the race
//  entirely.
// ---------------------------------------------------------------------------
using EnqueueFn = void* (*)(void*, void*, uint8_t, uint32_t, uint32_t);
using SetIsTameFn = bool (*)(void*, uint32_t, bool*);

EnqueueFn   g_enqueueTrampoline = nullptr;
SetIsTameFn g_setIsTame = nullptr;
detour::Hook g_hookEnqueue;

std::atomic<void*>    g_worldCtx{nullptr};
std::atomic<uint32_t> g_worldCtxCount{0};
std::atomic<int>      g_enqueueCount{0};
std::atomic<int>      g_sendCount{0};

// A tame request waiting to be issued on the game thread. 0 = none.
std::atomic<uint32_t> g_pendingTameEid{0};
std::atomic<int>      g_tameIssued{0};

// Re-entrancy guard: SetIsTame calls Enqueue, which is our hook.
thread_local bool t_inTame = false;

// --- component-write tracing -------------------------------------------------
//
// Enqueue zeroes the payload and returns; the CALLER then stamps `record+0xC`
// with the component type hash and fills the value. So, exactly like HitEvent,
// we cannot read the fields on the way in — we stash the record pointer and
// read it on the next call, by which time the caller has finished.
std::atomic<uint8_t*> g_pendingComp{nullptr};
std::atomic<int>      g_compSeen{0};

void FlushPendingComp() {
    uint8_t* rec = g_pendingComp.exchange(nullptr, std::memory_order_acquire);
    if (!rec) return;
    if (IsBadReadPtr(rec, 0x10)) return;

    uint32_t hash = 0;
    uint16_t size = 0;
    uint32_t eid  = 0;
    memcpy(&hash, rec + 0x0C, 4);
    memcpy(&size, rec + 0x00, 2);
    memcpy(&eid,  rec + 0x08, 4);

    const int n = g_compSeen.fetch_add(1) + 1;
    // Only the first few hundred are interesting, and only for named types —
    // the reflection table turns the hash into the component's qualified name,
    // which is what makes this trace readable.
    // Sampled trace. Logging every record stalled the game (25 MB of log
    // during world load made the render loop fail to present, and the user saw
    // "game creation failed"). The counters above stay accurate; only the
    // printf volume is bounded: first 200 records, then every 200th.
    if (n <= 200 || (n % 200) == 0) {
        const char* name = reflect::NameForHash(hash);
        if (name && name[0]) {
            WM_MOD_LOG("[wolfmount] COMP #%d %s (0x%08X) size=%u eid=%u",
                       n, name, hash, (unsigned)size, eid);
        } else {
            WM_MOD_LOG("[wolfmount] COMP #%d 0x%08X size=%u eid=%u",
                       n, hash, (unsigned)size, eid);
        }
    }
}

// --- world-context validation ----------------------------------------------
//
// We must not blindly hand the first `ctx` we see to SetIsTame: Enqueue is a
// generic queueing primitive and different callers may pass different
// containers. Reusing the wrong one would corrupt whatever sits at ctx+0x10.
//
// So we validate the shape SetIsTame relies on — `ctx+0x10` must look like a
// live queue {void* data; size_t capacity; u32 writeIndex; u32 count} — and we
// keep every distinct ctx we have seen in the log, so a mismatch is visible
// rather than silent.
constexpr size_t kQueueOffData      = 0x10;
constexpr size_t kQueueOffCapacity  = 0x18;
constexpr size_t kQueueOffWriteIdx  = 0x20;
constexpr size_t kQueueOffCount     = 0x24;

bool LooksLikeQueue(const void* ctx) {
    if (!ctx || IsBadReadPtr(ctx, 0x40)) return false;

    const auto* p = static_cast<const uint8_t*>(ctx);

    void*     data = nullptr;
    uint64_t  cap  = 0;
    uint32_t  widx = 0;
    uint32_t  count= 0;
    memcpy(&data,  p + kQueueOffData,     8);
    memcpy(&cap,   p + kQueueOffCapacity, 8);
    memcpy(&widx,  p + kQueueOffWriteIdx, 4);
    memcpy(&count, p + kQueueOffCount,    4);

    if (!data) return false;
    if (IsBadReadPtr(data, 16)) return false;
    if (cap < 16 || cap > (64ull << 20)) return false;
    if (widx > cap) return false;
    if (count > (1u << 24)) return false;
    return true;
}

// Distinct ctx pointers we have logged, so a second kind of caller is noticed.
constexpr int kMaxCtxKinds = 8;
void*  g_ctxKinds[kMaxCtxKinds] = {nullptr};
int    g_ctxKindCount = 0;

void NoteContext(void* ctx) {
    if (!ctx) return;
    for (int i = 0; i < g_ctxKindCount; ++i) {
        if (g_ctxKinds[i] == ctx) return;
    }
    if (g_ctxKindCount >= kMaxCtxKinds) return;
    g_ctxKinds[g_ctxKindCount++] = ctx;

    const bool ok = LooksLikeQueue(ctx);
    WM_MOD_LOG("[wolfmount] Enqueue ctx #%d = %p (queue-shaped: %d)%s",
               g_ctxKindCount, ctx, ok ? 1 : 0,
               ok ? "" : "  <-- rejected as world context");
}

// Faction of the last hit on each entity, so the menu can tell a wild wolf
// (FactionType 6) from a farm animal without another hook.
constexpr int kFactionSlots = 64;
struct FactionSlot {
    std::atomic<uint32_t> eid{0};
    std::atomic<uint8_t>  faction{0xFF};
};
FactionSlot g_factions[kFactionSlots];

void RememberFaction(uint32_t eid, uint8_t faction) {
    if (eid == 0) return;
    const int slot = int(eid % kFactionSlots);
    g_factions[slot].eid.store(eid, std::memory_order_relaxed);
    g_factions[slot].faction.store(faction, std::memory_order_relaxed);
}

void* DetourEnqueue(void* ctx, void* buf, uint8_t flags, uint32_t size,
                    uint32_t entityId) {
    // The record stashed by the PREVIOUS call is complete now — its caller has
    // already stamped the component hash. Read it before doing anything else.
    FlushPendingComp();

    // Learn the world context the first time the game writes anything. We only
    // adopt a ctx whose embedded queue actually validates, because SetIsTame
    // will write through exactly that queue.
    if (ctx && !g_worldCtx.load(std::memory_order_relaxed)) {
        NoteContext(ctx);
        if (LooksLikeQueue(ctx)) {
            g_worldCtx.store(ctx, std::memory_order_relaxed);
            WM_MOD_LOG("[wolfmount] world context ADOPTED: %p (queue data %p)",
                       ctx, [&] {
                           void* d = nullptr;
                           memcpy(&d, static_cast<uint8_t*>(ctx) + kQueueOffData, 8);
                           return d;
                       }());
        }
    }

    void* record = g_enqueueTrampoline
        ? g_enqueueTrampoline(ctx, buf, flags, size, entityId)
        : nullptr;

    int n = g_enqueueCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 200 || (n % 200) == 0) {
        WM_MOD_LOG("[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u",
                   n, ctx, entityId, size, (unsigned)flags);
    }

    // Stash the fresh record; its component hash is stamped by the caller
    // after we return, so it can only be read on the NEXT Enqueue.
    if (record) {
        g_pendingComp.store(static_cast<uint8_t*>(record),
                            std::memory_order_release);
    }

    // Issue a pending tame here, on the game thread, where the game itself
    // writes components. The guard stops SetIsTame's own Enqueue call from
    // re-entering this block.
    if (!t_inTame) {
        const uint32_t want = g_pendingTameEid.exchange(0, std::memory_order_acquire);
        if (want != 0 && g_setIsTame && ctx) {
            t_inTame = true;
            bool value = true;
            const bool ok = g_setIsTame(ctx, want, &value);
            const int issued = g_tameIssued.fetch_add(1) + 1;
            WM_MOD_LOG("[wolfmount] TAME issued eid=%u ok=%d (#%d)", want,
                       ok ? 1 : 0, issued);

            // Taming only stops the beast AI. To make the wolf an actual ally
            // it must also leave Faction 6 (WildBeast) for 11 (PlayerAlly).
            if (ok && g_allyOnTame.load(std::memory_order_relaxed)) {
                const uint8_t ally = game::kFactionPlayerAlly;
                const bool fok = SetFaction(want, ally);
                const int fn = g_factionIssued.fetch_add(1) + 1;
                WM_MOD_LOG("[wolfmount] FACTION queued eid=%u -> %u(%s) ok=%d (#%d)",
                           want, (unsigned)ally, game::FactionName(ally),
                           fok ? 1 : 0, fn);
            }
            t_inTame = false;
        }
    }

    return record;
}

// ---------------------------------------------------------------------------
//  Context accessor hook
//
//  `GetCtx` (0x9B0860) is the function the game calls whenever it needs the
//  world/entity admin:
//
//      void* GetCtx(void* store) { return *(void**)(*(void**)store + 8); }
//
//  Both the tame handler (0x14047D74C) and the PlayerInput submit path call it
//  and pass the return value straight to Enqueue as rcx. That return value is
//  exactly the ctx SetIsTame needs, so we hook the accessor and learn the ctx
//  the first time the game asks for it — independently of whether any
//  component write happens to occur.
//
//  The prologue is 0x48 0x8B 0x01 / 0x48 0x8B 0x40 0x08 / 0xC3 = 8 bytes, so
//  the 14-byte patch would run past the `ret` into the next function. We
//  therefore install a SHORT 5-byte `E9 rel32` jump instead (see detour.h
//  PatchMode::Rel32), which fits inside the 8-byte function exactly.
// ---------------------------------------------------------------------------
using GetCtxFn = void* (*)(void*);

GetCtxFn g_getCtxTrampoline = nullptr;
detour::Hook g_hookGetCtx;
std::atomic<int> g_ctxQueries{0};

// The `store` argument of GetCtx. `store+0x828` holds the entity table that
// ResolveEnt walks, so this is our handle on the whole entity list.
std::atomic<void*> g_entityStore{nullptr};

// The `store` that produced the world context we adopted. GetCtx computes
// `*(void**)(*(void**)store + 8)`, i.e. `world = store[0][1]`. QueryBuild
// (0x1409BAB60) expects exactly the inverse shape: `movq (%rcx),%r9` then
// `r9+0x4b0`, so the object it wants as rcx satisfies `rcx[0] == world`.
//
// `store` itself satisfies that: `store[0]` is the object GetCtx dereferenced,
// and `store[0]+8` is the world. Passing `store` as the holder therefore hands
// QueryBuild the very world GetCtx computed — with no assumption that the
// returned pointer is the same object.
std::atomic<void*> g_worldHolder{nullptr};

void* DetourGetCtx(void* store) {
    void* ctx = g_getCtxTrampoline ? g_getCtxTrampoline(store) : nullptr;
    g_ctxQueries.fetch_add(1, std::memory_order_relaxed);

    // Keep one such `store`: ResolveEnt (0x9B2E40) reads the entity table out of
    // `store+0x828`, which is the only handle we have on the full entity list.
    if (store && !g_entityStore.load(std::memory_order_relaxed)) {
        g_entityStore.store(store, std::memory_order_relaxed);
    }

    if (ctx && !g_worldCtx.load(std::memory_order_relaxed)) {
        if (LooksLikeQueue(ctx)) {
            g_worldCtx.store(ctx, std::memory_order_relaxed);
            if (store) g_worldHolder.store(store, std::memory_order_relaxed);
            WM_MOD_LOG("[wolfmount] world context ADOPTED via GetCtx: %p "
                       "(store %p)", ctx, store);
            // One-shot diagnostic: confirm the `store` really is the holder
            // whose [0] is the ECS world QueryBuild dereferences, before any
            // mod code ever hands it to the game.
            ProbeWorldCandidate(store);
        } else {
            NoteContext(ctx);
        }
    }
    return ctx;
}

} // anonymous namespace

void* WorldContext() { return g_worldCtx.load(std::memory_order_relaxed); }

// The object whose [0] is the ECS world, i.e. the `store` GetCtx was called
// with. This is the shape QueryBuild and every transformer handler expects as
// their rcx. Null until the world context has been adopted.
void* WorldHolder() { return g_worldHolder.load(std::memory_order_relaxed); }

bool HasWorldContext() { return WorldContext() != nullptr; }

bool TameEntity(uint32_t entityId, bool value) {
    if (entityId == 0) return false;
    if (!HasWorldContext()) return false;
    // Queue it; the Enqueue detour performs the write on the game thread.
    // `value == false` is not supported this way (untaming is a different
    // record), so we only handle the tame direction for now.
    if (!value) return false;
    g_pendingTameEid.store(entityId, std::memory_order_release);
    return true;
}

int KnownFaction(uint32_t entityId) {
    if (entityId == 0) return -1;
    const int slot = int(entityId % kFactionSlots);
    if (g_factions[slot].eid.load(std::memory_order_relaxed) != entityId) return -1;
    const uint8_t f = g_factions[slot].faction.load(std::memory_order_relaxed);
    return f == 0xFF ? -1 : int(f);
}

// ---------------------------------------------------------------------------
//  Generic byte-component write
//
//  Reproduces the record shape SetIsTame produces:
//      Enqueue(ctx, ctx+0x10, flags=3, size=0x6D, entityId) -> record
//      record[+0x00] = size (u16)        -- Enqueue already wrote this
//      record[+0x0C] = typeHash          -- payload begins here
//      record[+0x4C] = 1 (u16)           -- component-present marker
//      record[+0x6C] = value             -- payload + 0x60
// ---------------------------------------------------------------------------
bool WriteByteComponent(uint32_t entityId, uint32_t typeHash, uint8_t value) {
    void* ctx = WorldContext();
    if (!ctx || entityId == 0 || !g_enqueueTrampoline) return false;

    // Same arguments SetIsTame uses: buf = ctx+0x10 (the inline component
    // queue), entity id passed on the stack as the 5th argument.
    void* record = g_enqueueTrampoline(
        ctx,
        static_cast<uint8_t*>(ctx) + kQueueOffData,
        3,      // flags
        0x6D,   // size: 0x0C header + 0x60 value offset + 1 byte
        entityId);
    if (!record) return false;

    uint8_t* rec = static_cast<uint8_t*>(record);
    if (IsBadWritePtr(rec, 0x70)) return false;

    memcpy(rec + 0x0C, &typeHash, 4);
    uint16_t present = 1;
    memcpy(rec + 0x4C, &present, 2);
    rec[0x6C] = value;

    return true;
}

bool SetFaction(uint32_t entityId, uint8_t faction) {
    return WriteByteComponent(entityId, game::kHashFaction, faction);
}

int EnqueueCount() { return g_enqueueCount.load(std::memory_order_relaxed); }
int TameIssuedCount() { return g_tameIssued.load(std::memory_order_relaxed); }
int CtxQueryCount() { return g_ctxQueries.load(std::memory_order_relaxed); }

void SetTorchTameEnabled(bool on) {
    g_torchTame.store(on, std::memory_order_relaxed);
}
bool TorchTameEnabled() {
    return g_torchTame.load(std::memory_order_relaxed);
}
void SetAllyOnTameEnabled(bool on) {
    g_allyOnTame.store(on, std::memory_order_relaxed);
}
bool AllyOnTameEnabled() {
    return g_allyOnTame.load(std::memory_order_relaxed);
}
int FactionIssuedCount() {
    return g_factionIssued.load(std::memory_order_relaxed);
}
int TorchTameCount() {
    return g_torchTameCount.load(std::memory_order_relaxed);
}

void* EntityStore() {
    return g_entityStore.load(std::memory_order_relaxed);
}

bool HasEntityStore() { return EntityStore() != nullptr; }

// Mirrors ResolveEnt (0x9B2E40):
//     store   = *(void**)handle;          // we already hold `store`
//     table   = *(void**)(store + 0x828);
//     id      = *(uint32_t*)(table + (index - 1) * 8);
uint32_t ResolveEntity(uint32_t index) {
    if (index == 0) return 0;
    void* store = EntityStore();
    if (!store || IsBadReadPtr(store, 0x830)) return 0;

    void* table = nullptr;
    memcpy(&table, static_cast<uint8_t*>(store) + 0x828, 8);
    if (!table) return 0;

    const uint8_t* slot = static_cast<const uint8_t*>(table) +
                          (size_t)(index - 1) * 8;
    if (IsBadReadPtr(slot, 4)) return 0;

    uint32_t id = 0;
    memcpy(&id, slot, 4);
    return id;
}

int ScanEntities(uint32_t* out, int max) {    if (!out || max <= 0) return 0;
    void* store = EntityStore();
    if (!store || IsBadReadPtr(store, 0x830)) return 0;

    void* table = nullptr;
    memcpy(&table, static_cast<uint8_t*>(store) + 0x828, 8);
    if (!table) return 0;

    constexpr uint32_t kMaxIndex = 4096;
    int n = 0;
    for (uint32_t i = 1; i <= kMaxIndex && n < max; ++i) {
        const uint8_t* slot = static_cast<const uint8_t*>(table) + (size_t)(i - 1) * 8;
        if (IsBadReadPtr(slot, 4)) break;   // walked past the table
        uint32_t id = 0;
        memcpy(&id, slot, 4);
        // Entity ids are u16 on the wire; anything larger is uninitialised memory.
        if (id != 0 && id <= 0xFFFF) out[n++] = id;
    }
    return n;
}

uint32_t LastWildBeast() {
    return g_lastWildBeast.load(std::memory_order_relaxed);
}

// ---------------------------------------------------------------------------
//  Enemy -> Wildlife transformation
//
//  `wildlife_enemy_transformer` (rva 0x140480C70) is the engine's own program
//  for turning an Enemy unit into a Wildlife unit. Its body is:
//
//      QueryBuild(world, &buf)          // 0x1409BAB60
//      while (QueryRun(world, &buf))    // 0x1409B5A50  — false when stale
//          for each entity in buf's chunk array
//              if (componentPresent(entity, IsTame) && !(flags & 0x200))
//                  ComponentRemove(...) // 0x1409C5DF0
//          QueryNext(world, &buf)       // 0x1409B8010
//          ... flip the UnitMode byte the query descriptor points at ...
//
//  The `worldHolder` argument is any object whose +0 is the ECS world, which is
//  exactly the shape `GetCtx` returns (`*(void**)(*(void**)store + 8)`). The
//  world context we captured in DetourGetCtx is that pointer, so we can pass a
//  1-element holder on the stack.
//
//  The handler iterates EVERY entity the query matches, not just one, so this
//  is a whole-world pass. That is what we want for the summon/mount flow: any
//  wolf we later pick up is already a Wildlife unit by the time we tame it.
// ---------------------------------------------------------------------------
using TransformFn = void (*)(void*);

std::atomic<int> g_lastTransformCount{-1};

// ---------------------------------------------------------------------------
//  Probe: is the `store` we captured from GetCtx really the holder whose [0]
//  is the ECS world that QueryBuild (0x1409BAB60) expects?
//
//  QueryBuild's first two instructions are:
//      1409bab74: 4c 8b 09        movq (%rcx), %r9     ; r9 = *(void**)rcx
//      1409bab7d: 41 0f b6 81 b0 04 00 00  movzbl 0x4b0(%r9),%eax
//  So the handler's rcx must be a holder whose [0] is a world object, and that
//  world must have readable fields at +0x400..+0x4c0.
//
//  GetCtx is `mov rax,[rcx]; mov rax,[rax+8]; ret`, i.e. `world = store[0][1]`.
//  Feeding the store itself therefore satisfies QueryBuild exactly.
// ---------------------------------------------------------------------------
bool ProbeWorldCandidate(void* holder) {
    if (!holder || IsBadReadPtr(holder, 0x18)) {
        WM_MOD_LOG("[wolfmount] world probe: holder %p unreadable", holder);
        return false;
    }
    void* world = *reinterpret_cast<void**>(holder);
    if (!world || IsBadReadPtr(world, 0x4c8)) {
        WM_MOD_LOG("[wolfmount] world probe: holder[0]=%p not a readable world",
                   world);
        return false;
    }
    const auto* p = static_cast<const uint8_t*>(world);
    const uint8_t  b400 = p[0x400];
    const uint8_t  b470 = p[0x470];
    const uint8_t  b4b0 = p[0x4b0];
    const uint16_t w4b8 = *reinterpret_cast<const uint16_t*>(p + 0x4b8);
    const uint16_t w4ba = *reinterpret_cast<const uint16_t*>(p + 0x4ba);
    const uint8_t  b7a0 = p[0x7a0];
    const uint8_t  b7f0 = p[0x7f0];
    const void*    q1a8 = *reinterpret_cast<void* const*>(p + 0x1a8);
    WM_MOD_LOG("[wolfmount] world probe: holder=%p world=%p "
               "+0x400=%u +0x470=%u +0x4b0=%u +0x4b8=%u +0x4ba=%u "
               "+0x7a0=%u +0x7f0=%u +0x1a8=%p",
               holder, world, b400, b470, b4b0, w4b8, w4ba, b7a0, b7f0, q1a8);

    // DO NOT probe further out. `world` is a small object: only roughly the
    // first 0x500 bytes are committed. The ECS program registrar
    // (0x1409d5770) reads rcx+0x746350 and rcx+0xe15350 — 7.6 MB and 14.7 MB
    // past the object — so the registrar's rcx is a DIFFERENT, much larger
    // registry, not this `world`. Reading those offsets here faulted the game
    // (0xC0000005 at world+0xe15350); that probe was removed.
    //
    // What this means for the transformer: QueryBuild (0x1409BAB60) only reads
    // up to +0x4c0, which we just proved readable, so
    // wildlife_enemy_transformer can safely be handed this holder.
    WM_MOD_LOG("[wolfmount] world probe: +0x4b0..+0x4c0 readable -> "
               "QueryBuild-safe; NOT the program registry (that is 14.7MB out)");
    return true;
}

bool TransformEnemyToWildlife() {
    void* holder = WorldHolder();
    if (!holder) return false;

    const auto fn = reinterpret_cast<TransformFn>(
        reinterpret_cast<uintptr_t>(GameBase()) + rva::EnemyToWildlife);
    if (!fn) return false;

    // holder[0] is the ECS world. QueryBuild's first two instructions are
    //     movq (%rcx),%r9 ; movzbl 0x4b0(%r9),%eax
    // and all three transformer handlers (wildlife 0x480A70,
    // enemy->wildlife 0x480C70, farm 0x481060) hand that same rcx straight to
    // it, so passing the `store` GetCtx was called with gives QueryBuild the
    // world GetCtx itself computed — no assumption about the return value.
    //
    // WHY THIS IS DISABLED (verified crash, 2026-10-18):
    // Calling the transformer from the console (i.e. from the render thread,
    // at an arbitrary point in the frame) crashes the game at rva 0x9B8013:
    //     1409b8010: movq (%rcx),%rax
    //     1409b8013: movq 0x58(%rax),%rcx   <-- fault, rax = 0x440212
    // The transformer itself got past QueryBuild and QueryRun — the holder was
    // right — but the 0xa8-byte query object it builds on its own stack holds
    // pointers that are only valid while the game's own program dispatcher
    // drives this handler. Driven from outside, one of those pointers is
    // garbage and `world->[0x58]` faults.
    //
    // The correct way is to let the game invoke it: hook the dispatcher that
    // walks world+0x746350 (stride 0x1f20) and calls slot+0x28. That work is
    // not done yet, so the command reports NotAvailable instead of crashing.
    (void)fn;
    g_lastTransformCount.store(0, std::memory_order_relaxed);
    WM_MOD_LOG("[wolfmount] TransformEnemyToWildlife: REFUSED - the engine's "
               "wildlife_enemy_transformer can only be driven by the game's "
               "own dispatcher (see MODLOG crash post-mortem)");
    return false;
}

int LastTransformCount() {
    return g_lastTransformCount.load(std::memory_order_relaxed);
}

void Remove() {
    detour::Remove(&g_hookHit);
    detour::Remove(&g_hookEnqueue);
    detour::Remove(&g_hookGetCtx);
    g_active = false;
}

int Install() {
    uintptr_t base = GameBase();
    if (!base) {
        WM_MOD_LOG("[wolfmount] game hooks: game module not found");
        return 0;
    }

    int installed = 0;

    // Hook the ENTRY of SendEvent (0x140955400). Its prologue is
    //   48 83 EC 28   sub rsp, 0x28
    //   4C 8B D9      mov r11, rcx
    //   ...           (>= 14 bytes total, so the 14-byte patch fits cleanly)
    // Hooking the entry (rather than a call site) preserves the caller's
    // return address, which is what keeps the stack ABI-correct.
    void* target = reinterpret_cast<void*>(base + rva::SendEvent);

    // Sanity-check the known prologue. We compare only bytes that the loader
    // does NOT relocate, so this stays valid in memory.
    const uint8_t* tb = static_cast<const uint8_t*>(target);
    const uint8_t expect[5] = {0x48, 0x83, 0xEC, 0x28, 0x4C};
    if (memcmp(tb, expect, sizeof(expect)) != 0) {
        char got[16] = {0};
        for (int i = 0; i < 5; ++i) {
            snprintf(got + i * 2, sizeof(got) - i * 2, "%02X", tb[i]);
        }
        WM_MOD_LOG("[wolfmount] game hooks: SendEvent prologue mismatch "
                   "(got %s, game updated?). Aborting hook.", got);
        return 0;
    }

    WM_MOD_LOG("[wolfmount] game hooks: SendEvent entry verified "
               "(rva 0x%X, base %p, va %p)",
               (unsigned)rva::SendEvent, (void*)base, target);

    g_origSend = reinterpret_cast<SendEventFn>(base + rva::SendEvent);

    g_hookHit.target = target;
    g_hookHit.detour = reinterpret_cast<void*>(&DetourSendEvent);

    if (!CreateTrampoline(&g_hookHit)) {
        WM_MOD_LOG("[wolfmount] game hooks: trampoline creation failed");
        return 0;
    }

    // Calls must go through the trampoline (stolen prologue + jump back).
    g_trampoline = reinterpret_cast<SendEventFn>(g_hookHit.trampoline);

    if (!Install(&g_hookHit)) {
        WM_MOD_LOG("[wolfmount] game hooks: install failed");
        return 0;
    }

    g_active = true;
    ++installed;
    WM_MOD_LOG("[wolfmount] game hooks: SendEvent entry hook LIVE "
               "(trampoline %p, read-only)", g_hookHit.trampoline);

    // --- Enqueue: the component-write funnel, and how we learn the world ----
    // Prologue: 48 89 74 24 10   mov [rsp+0x10], rsi
    //           57               push rdi
    //           48 83 EC 20      sub rsp, 0x20
    // That is 12 bytes of whole instructions, so the 14-byte patch spills into
    // the next instruction cleanly.
    void* enqTarget = reinterpret_cast<void*>(base + rva::Enqueue);
    const uint8_t* eb = static_cast<const uint8_t*>(enqTarget);
    const uint8_t enqExpect[6] = {0x48, 0x89, 0x74, 0x24, 0x10, 0x57};
    if (memcmp(eb, enqExpect, sizeof(enqExpect)) != 0) {
        char got[16] = {0};
        for (int i = 0; i < 6; ++i) {
            snprintf(got + i * 2, sizeof(got) - i * 2, "%02X", eb[i]);
        }
        WM_MOD_LOG("[wolfmount] game hooks: Enqueue prologue mismatch (got %s). "
                   "Skipping Enqueue hook.", got);
        return installed;   // SendEvent hook is still live
    }

    g_setIsTame = reinterpret_cast<SetIsTameFn>(base + rva::SetIsTame);

    g_hookEnqueue.target = enqTarget;
    g_hookEnqueue.detour = reinterpret_cast<void*>(&DetourEnqueue);

    if (!CreateTrampoline(&g_hookEnqueue)) {
        WM_MOD_LOG("[wolfmount] game hooks: Enqueue trampoline failed");
        return installed;
    }
    g_enqueueTrampoline =
        reinterpret_cast<EnqueueFn>(g_hookEnqueue.trampoline);

    if (!detour::Install(&g_hookEnqueue)) {
        WM_MOD_LOG("[wolfmount] game hooks: Enqueue install failed");
        return installed;
    }
    ++installed;

    WM_MOD_LOG("[wolfmount] game hooks: Enqueue hook LIVE "
               "(rva 0x%X, SetIsTame %p)", (unsigned)rva::Enqueue,
               (void*)g_setIsTame);

    // --- GetCtx: learn the world context the moment the game asks for it ----
    // Prologue: 48 8B 01 / 48 8B 40 08 / C3 = 8 bytes total, so we must use the
    // 5-byte Rel32 patch; Abs64 would overwrite the `ret` and run into the next
    // function.
    void* ctxTarget = reinterpret_cast<void*>(base + rva::GetCtx);
    const uint8_t* cb = static_cast<const uint8_t*>(ctxTarget);
    const uint8_t ctxExpect[7] = {0x48, 0x8B, 0x01, 0x48, 0x8B, 0x40, 0x08};
    if (memcmp(cb, ctxExpect, sizeof(ctxExpect)) != 0) {
        char got[20] = {0};
        for (int i = 0; i < 7; ++i) {
            snprintf(got + i * 2, sizeof(got) - i * 2, "%02X", cb[i]);
        }
        WM_MOD_LOG("[wolfmount] game hooks: GetCtx prologue mismatch (got %s). "
                   "Skipping GetCtx hook.", got);
    } else {
        g_hookGetCtx.mode = detour::PatchMode::Rel32;
        g_hookGetCtx.target = ctxTarget;
        g_hookGetCtx.detour = reinterpret_cast<void*>(&DetourGetCtx);

        if (!CreateTrampoline(&g_hookGetCtx)) {
            WM_MOD_LOG("[wolfmount] game hooks: GetCtx trampoline failed");
        } else {
            g_getCtxTrampoline =
                reinterpret_cast<GetCtxFn>(g_hookGetCtx.trampoline);
            if (!detour::Install(&g_hookGetCtx)) {
                WM_MOD_LOG("[wolfmount] game hooks: GetCtx install failed");
            } else {
                WM_MOD_LOG("[wolfmount] game hooks: GetCtx hook LIVE "
                           "(rva 0x%X, trampoline %p)",
                           (unsigned)rva::GetCtx, g_hookGetCtx.trampoline);
                ++installed;
            }
        }
    }

    // Resolve the reflection types this mod depends on, so a mismatched build
    // is reported in the log rather than surfacing later as a wrong offset.
    const auto* hitType = reflect::ByName("keen::ecs::HitEvent");
    const auto* isTame   = reflect::ByName("keen::ecs::IsTame");
    WM_MOD_LOG("[wolfmount/reflect] HitEvent=%s (%u bytes) IsTame=%s",
               hitType ? "ok" : "MISSING", hitType ? hitType->size : 0u,
               isTame ? "ok" : "MISSING");

    return installed;
}

bool IsActive() { return g_active; }

} // namespace wolfmount::gamehooks
