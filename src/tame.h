#pragma once
// ============================================================================
//  WolfMount — taming rules (M3)
//
//  Pure decision logic, no game access. Verifiable in isolation.
// ============================================================================

#include <cstdint>

namespace wolfmount::tame {

// What the game told us about a death.
struct KillEvent {
    const char* victimTemplateGuid = nullptr;   // entity template GUID
    uint32_t    weaponItemId       = 0;         // itemId.value of the weapon
};

enum class Action {
    Ignore,          // let the game handle it normally
    ConvertToTame,   // turn this kill into a tame
};

struct Decision {
    Action     action = Action::Ignore;
    const char* reason = "";

    bool wasWolf      = false;
    bool wasTorch     = false;
    bool alreadyOwned = false;
};

// Observable counters, surfaced in the mod menu.
struct State {
    int tamedCount          = 0;   // 0 or 1 — only one wolf may be tamed
    int convertedKills      = 0;   // torch kills that became tames
    int ignoredKills        = 0;   // torch kills skipped because one is owned
    int wolfKillsWithoutTorch = 0; // wolves killed by other means

    const char* tamedGuid = nullptr;
};

// True if `guid` names one of the wolf entity templates in the shipped data.
bool IsWolfTemplate(const char* guid);

// Apply the taming rules to a death event.
Decision OnEntityKilled(const KillEvent& ev);

State  Snapshot();
void   Reset();

const char* RulesText();

} // namespace wolfmount::tame
