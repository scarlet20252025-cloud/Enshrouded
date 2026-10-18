#pragma once
// ============================================================================
//  WolfMount — combat follow plan (M4)
//
//  Derived entirely from the shipped component data. See follow.cpp for the
//  evidence behind each decision.
// ============================================================================

#include <cstring>
#include <vector>

namespace wolfmount::follow {

struct FactionChange {
    const char* from = "WildBeast";   // what a wolf ships as
    const char* to   = "PlayerAlly";  // what makes it an ally
    bool valid = false;
};

struct Plan {
    FactionChange faction;

    bool addIsTame        = false;   // suppresses hostile wildlife behaviour
    bool addAnimal        = false;   // animal marker
    bool addAnimalSaved   = false;   // persists across save/load
    bool addNetworkAnimal = false;   // replicates to other players
    bool keepCombatAI     = false;   // wolf already has the full stack
    bool keepAggroEnemyValue = false;// must stay true, unlike tameable pets
    bool followViaSpawnFlag = false; // AdminSpawnCommand.followPlayer

    const char* isTameMeaning = "";
    std::vector<const char*> avoidComponents;
    bool valid = false;
};

// Compute the plan and validate it.
Plan BuildPlan();

// Human readable summary for the mod menu.
const char* Describe(const Plan& p);

} // namespace wolfmount::follow
