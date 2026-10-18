#pragma once
// ============================================================================
//  WolfMount — runtime ECS bridge
//
//  M2 starts by PROVING the ECS command surface is reachable from inside the
//  game process. We locate the admin-command strings in the executable and
//  report what we found. Nothing is called until a target is verified.
// ============================================================================

#include <windows.h>
#include <cstdint>

namespace wolfmount::ecs {

struct ProbeResult {
    const char* status = "not probed";

    HMODULE    module = nullptr;
    int        featuresFound = 0;

    // Each of these is a virtual address inside the game module, or 0.
    uintptr_t  adminSpawnCommandStr = 0;
    uintptr_t  adminEnemyActionStr = 0;
    uintptr_t  isTameDocStr = 0;
    uintptr_t  tameWildlifeEventStr = 0;
    uintptr_t  hookAnchorStr = 0;
    uintptr_t  hierarchyStr = 0;
    uintptr_t  companionAIStr = 0;

    const char* adminSpawnCommandSection = "";

    bool hasAdminSpawnCommand = false;   // spawn a wolf near the player
    bool hasAdminEnemyAction = false;    // carries EnemyDebugAction::SetTamed
    bool hasIsTameSemantics = false;     // the tamed-flag behaviour docstring
    bool hasTameWildlifeEvent = false;   // the taming event type
    bool hasHookAnchor = false;          // the wolf's own back attachment
    bool hasImpactHierarchy = false;     // parent/child entity hierarchy
    bool hasCompanionAI = false;         // the fighting companion behaviour
};

// Run the probe once; safe to call repeatedly.
const ProbeResult& Probe();

} // namespace wolfmount::ecs
