#pragma once
// ============================================================================
//  WolfMount — game data constants
//
//  Every GUID and enum value in this file was extracted from the shipped 1.0
//  game data with `kfc-parser unpack`. Nothing here is guessed.
//  See MODLOG.md for the extraction method and the raw evidence.
// ============================================================================

#include <cstdint>

namespace wolfmount::game {

// ---------------------------------------------------------------------------
//  Faction enum — AUTHORITATIVE values
//
//  Source: reflection_data.json type `keen::FactionType` (index 2066, enum with
//  16 values). An earlier version of this file guessed a different ordering;
//  the numbers below are read straight out of the shipped binary's reflection
//  table and are the only correct ones.
// ---------------------------------------------------------------------------
enum class Faction : uint8_t {
    Environment     = 0,
    HitAll          = 1,
    Fogger          = 2,
    Vukah           = 3,
    Scavenger       = 4,
    Wildlife        = 5,    // dogs / cats / rabbits / pheasants
    WildBeast       = 6,    // <-- what a wolf currently is
    Player          = 7,
    AutomatedPlayer = 8,
    HitOthers       = 9,
    Skeleton        = 10,
    PlayerAlly      = 11,   // <-- what a tamed companion must become
    FarmAnimal      = 12,   // sheep / goats / yaks
    Cyclops         = 13,
    Drak            = 14,
    Ancients        = 15,
};

inline const char* FactionName(uint8_t v) {
    switch (v) {
        case 0:  return "Environment";
        case 1:  return "HitAll";
        case 2:  return "Fogger";
        case 3:  return "Vukah";
        case 4:  return "Scavenger";
        case 5:  return "Wildlife";
        case 6:  return "WildBeast";
        case 7:  return "Player";
        case 8:  return "AutomatedPlayer";
        case 9:  return "HitOthers";
        case 10: return "Skeleton";
        case 11: return "PlayerAlly";
        case 12: return "FarmAnimal";
        case 13: return "Cyclops";
        case 14: return "Drak";
        case 15: return "Ancients";
        default: return "?";
    }
}

// Plain constants so call sites do not have to spell out the enum cast.
constexpr uint8_t kFactionWildBeast  = 6;
constexpr uint8_t kFactionPlayer     = 7;
constexpr uint8_t kFactionPlayerAlly = 11;
constexpr uint8_t kFactionFarmAnimal = 12;

// ---------------------------------------------------------------------------
//  Component type hashes — FNV-1a-32 of the qualified type name
//
//  The engine identifies a component by this hash, which is why the write path
//  stamps it into the record at +0x0C. Values verified against
//  reflection_data.json (type `qualifiedHash`) AND by recomputing the FNV hash
//  of the name, so a typo here cannot silently target the wrong component.
// ---------------------------------------------------------------------------
constexpr uint32_t kHashFaction          = 0xA1F30F21;  // keen::ecs::Faction
constexpr uint32_t kHashIsTame           = 0x1399E0BA;  // keen::ecs::IsTame
constexpr uint32_t kHashCurrentTransform = 0x027AC564;  // keen::ecs::CurrentTransform
constexpr uint32_t kHashPlayerFocus      = 0x6BA7F22A;  // keen::ecs::PlayerFocus
constexpr uint32_t kHashAnimal           = 0x8FB61D93;  // keen::ecs::Animal

// ---------------------------------------------------------------------------
//  Entity templates
// ---------------------------------------------------------------------------

// --- wolves (the mount candidates) -----------------------------------------
constexpr const char* kWolfEarlygame   = "478381c5-585f-4264-b373-dbb1ea596eca";
constexpr const char* kWolfHeavy       = "f6a96b72-6da4-4e04-ab62-40e8d0feeac7";
constexpr const char* kWolfAutoTest    = "0d75b9a9-7e48-4f3a-bf2a-19bf6021f531";
constexpr const char* kWolfHookAG2     = "54c99a9f-d6d1-4cd9-84bb-dd001915ca98";
constexpr const char* kWolfBossHeavy   = "ca98115b-71a2-4de2-9418-cf8d34b75ce3";

// --- the wolf's own hook anchor (exists on every wolf in the base game) ----
//  attachmentSlot "Root", localOffset (0, 1, 0)
constexpr const char* kWolfHookAnchor  = "ab078982-f5f1-40be-999e-ecaf37d7f112";
constexpr const char* kWolfHookAnchorHeavy = "3acddc45-b8dc-4c0b-878c-010d5c85b7ac";

// --- dogs (the "copy the dog" target) --------------------------------------
constexpr const char* kDogBright       = "5d9c1829-69fc-4339-8bcc-5e62e63e9a31";
constexpr const char* kDogDotted       = "74bda2f0-74ab-4bad-851e-2328c808daf0";
constexpr const char* kDogDark         = "406d4e1c-594b-4816-8b8d-77cfef1e83bc";
constexpr const char* kDogBlack        = "68c37a11-69c9-476b-9117-ef85226a086e";
constexpr const char* kDogWhite        = "51d37581-38fc-4741-9e4c-1dc85463ec67";

// --- cats ------------------------------------------------------------------
constexpr const char* kCatBlack        = "1ce5ac27-d8b1-4fa8-92db-f568994d080f";
constexpr const char* kCatStriped      = "60065215-15ca-424c-9bc3-5665685fed60";
constexpr const char* kCatBright       = "8d2e50d2-ed98-4231-9846-ca1b7fb69041";

// --- companion archetypes --------------------------------------------------
//  Base_Companion is a COMPLETE fighting companion: 86 components including
//  CombatTargetActor, ControlCombatTarget, Enemy01BehaviorState, PathFinder,
//  PathWalker, SteeringLocomotion, Aggro. Faction: Player.
constexpr const char* kBaseCompanion       = "2a931d54-81e9-4ee4-86c4-27271b0ea5a3";
constexpr const char* kWildlifeCompanion   = "f2358637-5ce7-4925-bda5-ca68fab94700";
constexpr const char* kCompanionTest       = "83fa0d96-c6bc-4c0a-a9bc-88494938fa19";

// --- tameable animal base classes ------------------------------------------
constexpr const char* kBaseTameable        = "4cbd184f-3236-481d-8862-f9dd264766d3";
constexpr const char* kBaseTameablePetOnly = "095bb39c-1428-411e-ac36-a784563b4256";
constexpr const char* kBaseTameableTransform = "08365b0a-2205-45d7-8f02-fecabd5d32db";
constexpr const char* kBaseTameableAG2     = "a2ee105d-d9d8-4a86-bffb-21a2cccd2756";
constexpr const char* kBaseNonTameable     = "ada12d9e-eeb5-4b28-ae88-1e34ac57c22b";

// --- spawnpoints -----------------------------------------------------------
constexpr const char* kSpawnWolfEarlygame  = "1e0b74fd-9ea3-42ec-b495-8e72e94f6667";
constexpr const char* kSpawnWolfPOI        = "bf4ae22e-9f66-43da-bd75-9f1c3da3b69e";
constexpr const char* kSpawnWolfHeavy      = "c2ccb01e-4051-45d6-8ee0-0498486019a3";
constexpr const char* kSpawnDog01          = "0c2ebb2d-a072-4d69-9165-80795080364d";

// ---------------------------------------------------------------------------
//  Torch items — the taming weapon
//
//  Read from ItemInfo in the shipped data. Torch01-03 are Weapons/MeleeWeapon;
//  Torch04 (GleamRoot, the underwater torch) is Tools/MidRangeWeapon.
//  `itemId.value` is the runtime integer the damage path carries, so that is
//  what the kill filter compares against.
// ---------------------------------------------------------------------------
struct TorchDef {
    const char* name;
    const char* guid;
    uint32_t    itemId;
    const char* category;
    const char* slot;
};

constexpr TorchDef kTorches[] = {
    { "Tool_Torch01", "224097e5-ed0d-49d2-9d23-43256a6682b3",
      3474096535u, "Weapons", "MeleeWeapon" },
    { "Tool_Torch02_Resin", "9871b3cb-d75d-43dc-ae93-e735c9c4b248",
      531354159u, "Weapons", "MeleeWeapon" },
    { "Tool_Torch03_Wax", "a8ea061b-7ab6-4065-8687-3ca3af2fdbb8",
      3913483832u, "Weapons", "MeleeWeapon" },
    { "Tool_Torch04_GleamRoot_UnderWater", "fbf42f49-5ab3-4806-b550-4eed4caf6ac3",
      32289505u, "Tools", "MidRangeWeapon" },
};

constexpr int kTorchCount = (int)(sizeof(kTorches) / sizeof(kTorches[0]));

// True if `itemId` is any of the four torches.
inline bool IsTorch(uint32_t itemId) {
    for (int i = 0; i < kTorchCount; ++i) {
        if (kTorches[i].itemId == itemId) return true;
    }
    return false;
}

// ---------------------------------------------------------------------------
//  Entity component type names (for the ECS layer, used from M4 onward)
// ---------------------------------------------------------------------------
constexpr const char* kCompFaction        = "keen::ecs::Faction";
constexpr const char* kCompAnimal         = "keen::ecs::Animal";
constexpr const char* kCompAnimalSaved    = "keen::ecs::AnimalSaved";
constexpr const char* kCompIsTame         = "keen::ecs::IsTame";
constexpr const char* kCompNetworkAnimal  = "keen::ecs::NetworkAnimal";
constexpr const char* kCompHookAnchorSub  = "keen::ecs::HookShotAnchorSubEntity";
constexpr const char* kCompSubEntities    = "keen::ecs::SubEntities";
constexpr const char* kCompImpactHierarchy= "keen::ecs::ImpactHierarchy";
constexpr const char* kCompCombatTarget   = "keen::ecs::CombatTargetActor";
constexpr const char* kCompBehaviorState  = "keen::ecs::Enemy01BehaviorState";
constexpr const char* kCompInteractionOffer = "keen::ecs::ClientInteractionOffer";

} // namespace wolfmount::game
