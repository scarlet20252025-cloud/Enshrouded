// ============================================================================
//  WolfMount — taming state machine (M3)
//
//  Rules the mod must enforce:
//    1. Killing a wolf WITH A TORCH tames it instead of killing it.
//    2. Only ONE wolf may ever be tamed.
//    3. Once a wolf is tamed, further torch kills do nothing.
//
//  The kill itself happens inside the game's damage path. This module owns the
//  DECISION: given a death event (victim + weapon itemId), decide whether the
//  mod should convert the kill into a tame, and record the outcome.
//
//  It deliberately does NOT reach into the game's ECS. Turning a decision into
//  a component change needs the dispatcher address, which is M4/M5 work. Until
//  then this module is the testable, verifiable core.
// ============================================================================

#include "tame.h"
#include "gamedata.h"

#include <atomic>
#include <mutex>
#include <vector>

namespace wolfmount::tame {

namespace {

std::mutex g_mu;
State      g_state;

} // anonymous namespace

// ---------------------------------------------------------------------------
//  IsWolfTemplate
//
//  Compares against the extracted wolf GUIDs. The caller passes whatever the
//  game reports as the entity's template; we accept an exact match on any of
//  the five wolf templates.
// ---------------------------------------------------------------------------
bool IsWolfTemplate(const char* guid) {
    if (!guid) return false;
    static const char* kWolves[] = {
        game::kWolfEarlygame,
        game::kWolfHeavy,
        game::kWolfAutoTest,
        game::kWolfHookAG2,
        game::kWolfBossHeavy,
    };
    for (auto* w : kWolves) {
        if (strcmp(w, guid) == 0) return true;
    }
    return false;
}

// ---------------------------------------------------------------------------
//  OnEntityKilled — the taming decision
//
//  Returns what the mod should do with this death. Never throws, never touches
//  game memory.
// ---------------------------------------------------------------------------
Decision OnEntityKilled(const KillEvent& ev) {
    std::lock_guard<std::mutex> lk(g_mu);

    Decision d{};
    d.wasWolf     = IsWolfTemplate(ev.victimTemplateGuid);
    d.wasTorch    = game::IsTorch(ev.weaponItemId);
    d.alreadyOwned = g_state.tamedCount > 0;

    // Rule 3: a wolf already tamed — no further taming from torch kills.
    if (d.alreadyOwned) {
        d.action = Action::Ignore;
        d.reason = "a wolf is already tamed";
        g_state.ignoredKills++;
        return d;
    }

    // Rule 1: wolf + torch => tame instead of kill.
    if (d.wasWolf && d.wasTorch) {
        d.action = Action::ConvertToTame;
        d.reason = "wolf killed with a torch";
        g_state.tamedCount++;
        g_state.tamedGuid = ev.victimTemplateGuid;
        g_state.convertedKills++;
        return d;
    }

    // Anything else is an ordinary death; the mod stays out of the way.
    d.action = Action::Ignore;
    if (!d.wasWolf)      d.reason = "victim is not a wolf";
    else if (!d.wasTorch) d.reason = "weapon is not a torch";
    else                  d.reason = "no rule matched";

    if (d.wasWolf && !d.wasTorch) g_state.wolfKillsWithoutTorch++;
    return d;
}

// ---------------------------------------------------------------------------
//  Introspection (used by the menu and by tests)
// ---------------------------------------------------------------------------
State Snapshot() {
    std::lock_guard<std::mutex> lk(g_mu);
    return g_state;
}

void Reset() {
    std::lock_guard<std::mutex> lk(g_mu);
    g_state = State{};
}

// ---------------------------------------------------------------------------
//  A short human-readable rule summary, shown in the mod menu.
// ---------------------------------------------------------------------------
const char* RulesText() {
    return "火把击杀狼 = 驯化 | 全游戏仅一头 | 已驯化后火把击杀无效";
}

} // namespace wolfmount::tame
