#pragma once
// ============================================================================
//  WolfMount — game hooks (M3/M6)
//
//  Installs inline hooks on the event-system call sites located by static
//  analysis, so the mod can observe deaths and synthesise tames.
//
//  All image addresses are relative to image base 0x140000000; the runtime
//  installer adds the actual module base (ASLR-safe).
// ============================================================================

#include <cstdint>

namespace wolfmount::gamehooks {

// Image-base-relative addresses (RVA) located by static analysis.
namespace rva {
    // The event writer: writes {hash(edx), size(r8d), entityId(r9d)} into the
    // event buffer at rcx. Returns the event record pointer.
    constexpr uint32_t SendEvent      = 0x955400;

    // The COMPONENT writer — the other half of the pipeline. SendEvent carries
    // local presentation events; Enqueue is what actually lands component data
    // in the world:
    //
    //     void* Enqueue(void* ctx,      // rcx — the world / entity admin
    //                   void* buf,      // rdx — ctx+0x10 for the inline queue
    //                   uint8_t flags,  // r8b
    //                   uint32_t size,  // r9d — total payload size
    //                   uint32_t eid)   // stack — the target entity id
    //
    // It returns the record; `record + 0xC` is the payload, whose first 4 bytes
    // are the component-type hash and whose remaining bytes are the component
    // value (the component's own field offsets apply from payload + dataOffset).
    //
    // 215 call sites. `SetIsTame` (0x47D040) is one of them, which is how we
    // know the argument shape above.
    constexpr uint32_t Enqueue        = 0x952400;

    // bool SetIsTame(void* ctx, uint32_t entityId, bool* value)
    // A ready-made, self-contained component setter: it calls Enqueue itself and
    // writes the IsTame component. Not called directly anywhere in the image
    // (0 call sites), so we are free to call it with a ctx we recovered.
    constexpr uint32_t SetIsTame      = 0x47D040;

    // THE context accessor — the single most reliable way to obtain the world
    // ctx, because it is *the* function the game itself calls whenever it needs
    // it (396 call sites):
    //
    //     void* GetCtx(void* store)  { return *(void**)(*(void**)store + 8); }
    //
    //     1409b0860: 48 8B 01        mov rax, [rcx]
    //     1409b0863: 48 8B 40 08     mov rax, [rax+8]
    //     1409b0867: C3              ret
    //
    // Both the tame handler (0x14047D74C) and the PlayerInput submit path
    // (0x1402CB..) call it and then hand the RESULT straight to Enqueue as rcx,
    // which is exactly the ctx SetIsTame needs. Hooking it therefore yields the
    // world context on return, without waiting for any component write.
    constexpr uint32_t GetCtx         = 0x9B0860;

    // HitEvent send sites: `mov edx, 0xCC0D57E0; mov r8d, 0xF8; call send`.
    // HitEvent carries everything the taming rule needs.
    constexpr uint32_t HitSendSiteA   = 0x3E93A1;   // mov edx, HitEvent
    constexpr uint32_t HitSendSiteB   = 0x3EFA7C;   // mov edx, HitEvent

    // EntityDiedEvent send site: `mov edx, 0xD8EC982A; mov r8d, 0x10`.
    // Only carries deadEntityId, so it is NOT sufficient for the torch rule.
    constexpr uint32_t DeathSendSite1 = 0x25F7FB;

    // TameWildlifeEvent handler: `cmp hash, 0x537B675C; jne skip`.
    constexpr uint32_t TameHandler    = 0x47D718;

    // The ECS query helpers behind wildlife_enemy_transformer:
    //     void QueryBuild(void* world, void* outBuf0xA8);
    //     bool QueryRun  (void* world, void* buf);   // false when stale
    //     void QueryNext (void* world, void* buf);   // advance to next chunk
    //     void ComponentRemove(void* owner, u16 idx, u8 a, void* b, void* c,
    //                          void* d);
    //
    // wildlife_enemy_transformer (0x140480c70) chains exactly these four to flip
    // an entity's UnitMode byte between Wildlife(0) and Enemy(1). See MODLOG.
    constexpr uint32_t QueryBuild     = 0x9BAB60;
    constexpr uint32_t QueryRun       = 0x9B5A50;
    constexpr uint32_t QueryNext      = 0x9B8010;
    constexpr uint32_t ComponentRemove= 0x9C5DF0;

    // wildlife_enemy_transformer itself: void Transform(void* worldHolder)
    // where worldHolder[0] is the ECS world. 0 call sites in the image.
    constexpr uint32_t EnemyToWildlife = 0x480C70;

    // wildlife handler: void WildlifeProgram(void* worldHolder). The program that
    // owns the Wildlife/Animal component set (FleeSensor, PathWalker, ...).
    // 0 call sites in the image either.
    constexpr uint32_t WildlifeProgram = 0x480A70;

    constexpr uint32_t HitEventSize   = 0xF8;      // 248 bytes
    constexpr uint32_t HitEventHash   = 0xCC0D57E0;
}

// HitEvent field offsets inside the 248-byte record.
// Source of truth: tools/kfc/reflection_data.json, type `keen::ecs::HitEvent`
// (index 3298, size 248, 22 fields). Offsets are relative to the payload
// pointer returned by SendEvent (record + 8).
namespace hit {
    constexpr size_t RootTargetId   = 160;   // victim entity id
    constexpr size_t SourceId       = 164;   // attacker entity id (the player)
    constexpr size_t PermissionSrc  = 168;
    constexpr size_t WeaponPideId   = 172;   // runtime item instance id, NOT a template id
    constexpr size_t ArmorPideId    = 176;
    constexpr size_t HitAngle       = 180;   // float32
    constexpr size_t Range          = 184;   // float32
    constexpr size_t HealthChange   = 188;   // sint32
    constexpr size_t StaminaChange  = 192;
    constexpr size_t SpecialGain    = 196;
    constexpr size_t Aggro          = 200;   // float32
    constexpr size_t NoiseRange     = 204;   // float32
    constexpr size_t HitCounter     = 208;   // uint16
    constexpr size_t ImpactId       = 212;   // keen::impact::ImpactId { uint32 id }
    constexpr size_t WeaponCategory = 216;   // keen::WeaponCategoryId (uint32)
    constexpr size_t DamageTypes    = 220;   // uint16 mask
    constexpr size_t AttackCategory = 223;   // uint8 mask
    constexpr size_t HitReaction    = 224;   // enum uint16
    constexpr size_t PushBackForce  = 226;
    constexpr size_t AttackerStates = 232;   // uint64 mask
    constexpr size_t TargetFaction  = 240;   // keen::FactionType (uint8)
}

// Install all hooks. Returns the number of hooks that succeeded.
int Install();

// Remove all hooks.
void Remove();

// True once the hooks are active.
bool IsActive();

// ---------------------------------------------------------------------------
//  Write path
//
//  `Enqueue` is the single funnel every component write goes through, and its
//  first argument is the world/entity admin — the `ctx` that `SetIsTame` needs.
//  We therefore learn `ctx` passively from the hook instead of pointer-chasing
//  for it: the first component the game writes hands us the world.
// ---------------------------------------------------------------------------

// The world/entity admin pointer learned from `Enqueue`. Null until the game
// writes its first component (which happens within a frame or two of loading).
void* WorldContext();

// True once WorldContext() is usable.
bool HasWorldContext();

// Tame `entityId` by calling the game's own `SetIsTame`. Returns false when the
// world context is not known yet or the call was rejected.
//
// This is a real component write through the game's own code path — it enqueues
// the exact same IsTame component record the game itself would write, so the
// engine treats the taming as genuine (saved, networked, visible to AI).
bool TameEntity(uint32_t entityId, bool value);

// Faction of an entity, read from the last HitEvent that involved it, or -1.
// Used to confirm we are looking at a wild wolf (FactionType 6 = WildBeast).
int KnownFaction(uint32_t entityId);

// The most recent entity we saw on the receiving end of a HitEvent whose
// faction was `WildBeast` (6) — i.e. a live wolf we can call SetIsTame on.
// Returns 0 when no wolf has been hit yet.
uint32_t LastWildBeast();

// How many times the game asked for its world context (GetCtx hook).
int CtxQueryCount();

// Component writes observed through the Enqueue hook (a liveness signal: it
// stays 0 in the main menu and starts moving as soon as a world loads).
int EnqueueCount();

// How many SetIsTame writes this mod has actually performed.
int TameIssuedCount();

// ---------------------------------------------------------------------------
//  Torch-kill taming (M3)
//
//  When enabled, a HitEvent whose damage type includes Magical_Fire (the torch)
//  and whose victim is a wild beast (Faction 6) arms a pending tame: the very
//  next Enqueue on the game thread performs the SetIsTame write. Doing the
//  write from inside Enqueue is deliberate — Enqueue mutates the queue's
//  write index, so writing from the render thread would corrupt it.
// ---------------------------------------------------------------------------

// Turn automatic torch-kill taming on/off. Default: on.
void SetTorchTameEnabled(bool on);
bool TorchTameEnabled();

// When on, a torch-tamed wolf is ALSO moved from Faction 6 (WildBeast) to
// Faction 11 (PlayerAlly), so it becomes a fighting companion rather than just
// a docile animal. Default: on.
void SetAllyOnTameEnabled(bool on);
bool AllyOnTameEnabled();

// How many tames the torch rule has triggered by itself.
int TorchTameCount();

// ---------------------------------------------------------------------------
//  Entity table (read-only)
//
//  `GetCtx(store)` takes a `store` whose `+0x828` field is the u32 entity table
//  that `ResolveEnt` (0x9B2E40) walks: entry i at (store+0x828)[ (i-1)*8 ].
//  We keep the first such store the game hands us, which lets the menu look at
//  live entity ids without any further hooks.
// ---------------------------------------------------------------------------

// The `store` pointer captured from GetCtx. Null until the game calls it.
void* EntityStore();

// True once EntityStore() is usable.
bool HasEntityStore();

// Resolve an entity-table index to an entity id, exactly like the game's own
// ResolveEnt. Returns 0 when the index is empty or the store is not known yet.
uint32_t ResolveEntity(uint32_t index);

// Scan the entity table for ids in [1, 4096) that the game currently knows
// about, writing up to `max` of them into `out`. Returns how many were written.
//
// This is the lookup the summon path needs: once the player is standing next to
// a wolf, its entity id is in this table, and we can offer it by distance.
int ScanEntities(uint32_t* out, int max);

// ---------------------------------------------------------------------------
//  Faction change (wild wolf -> player ally)
//
//  Taming alone only stops the beast AI from running; the animal still belongs
//  to Faction 6 (WildBeast) and is therefore still an enemy. To get a companion
//  that fights alongside the player we must also move it to Faction 11
//  (PlayerAlly).
//
//  The write is QUEUED and performed on the game thread inside the next
//  Enqueue, because Enqueue mutates the queue's write index — issuing it from
//  the render thread would corrupt that queue.
// ---------------------------------------------------------------------------
bool SetFaction(uint32_t entityId, uint8_t faction);

// ---------------------------------------------------------------------------
//  Enemy -> Wildlife transformation (M6)
//
//  The engine's own `wildlife_enemy_transformer` program (rva 0x480C70) walks
//  the entity table with its ECS query helpers and flips the entity's
//  `UnitTransformer` mode byte: 0 = Wildlife, 1 = Enemy. Flipping a wolf from
//  Enemy to Wildlife is the prerequisite for every taming path, because
//  `TameWildlifeEvent` and the whole taming pipeline only act on entities that
//  carry the Animal/Wildlife component set (verified in MODLOG).
//
//  We call the game's own code rather than reimplementing the query, so the
//  transformation is indistinguishable from the game doing it itself.
// ---------------------------------------------------------------------------

// Run the game's enemy->wildlife transformation. `holder` must be an object
// whose first field is the ECS world pointer (the same shape GetCtx returns
// from: `*(void**)(*(void**)store + 8)`). Returns false when the world context
// is not known yet.
bool TransformEnemyToWildlife();

// Diagnostic: read the fields QueryBuild (0x1409BAB60) dereferences out of a
// candidate holder pointer and log them. Returns false when the pointer is not
// readable at all. Used to confirm the `store` captured from GetCtx really is
// the holder whose [0] is the ECS world, before we hand it to the game's code.
bool ProbeWorldCandidate(void* holder);

// The object whose [0] is the ECS world, i.e. the `store` GetCtx was called
// with. This is the shape QueryBuild and every transformer handler expects as
// their rcx. Null until the world context has been adopted.
void* WorldHolder();

// How many entities the last TransformEnemyToWildlife() pass reported
// transforming. -1 when no pass has run yet.
int LastTransformCount();


// The primitive behind SetFaction: write any 1-byte tag component.
//
// `SetIsTame` is one instance of a general shape the game uses for every 1-byte
// tag component:
//     Enqueue(ctx, ctx+0x10, flags=3, size=0x6D, entityId);
//     record[+0x0C] = typeHash;   // payload starts here
//     record[+0x4C] = 1;          // u16 component-present marker
//     record[+0x6C] = value;      // payload + 0x60
// Replicating it exactly is what makes the engine treat the write as genuine.
bool WriteByteComponent(uint32_t entityId, uint32_t typeHash, uint8_t value);

// How many faction writes this mod has performed.
int FactionIssuedCount();

} // namespace wolfmount::gamehooks
