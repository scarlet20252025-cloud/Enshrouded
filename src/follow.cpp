// ============================================================================
//  WolfMount — combat follow plan (M4)
//
//  Goal: make the tamed wolf fight alongside the player.
//
//  What the shipped data proved:
//
//    * The wolf ALREADY has the full combat AI stack — CombatTargetActor,
//      ControlCombatTarget, SelectedTargets, Enemy01BehaviorState,
//      PathFinder, PathWalker, SteeringLocomotion, EnemyArsenalReference,
//      and `Aggro.applyEnemyValue = true`. Wolves are hostile fighters.
//
//    * What makes an animal a friendly follower is not extra AI. It is:
//        - Faction: Wildlife -> Player (or PlayerAlly)
//        - keen::ecs::IsTame present, which per the shipped docstring stops
//          the Wildlife behaviour: "If set to false the Wildlife behavior
//          won't run if the Wildlife is tamed(has the IsTame component)"
//        - keen::ecs::Animal / AnimalSaved / NetworkAnimal so it persists and
//          replicates
//
//    * `Base_Companion` (faction Player, Aggro.applyEnemyValue true, 86
//      components) is the reference fighting-companion archetype. The wolf's
//      own component set is already a superset in the areas that matter.
//
//  So M4 is a PATCH PLAN, not new AI. This module computes the exact field
//  changes and validates them, without touching the game.
// ============================================================================

#include "follow.h"
#include "gamedata.h"

#include <cstdio>

namespace wolfmount::follow {

// ---------------------------------------------------------------------------
//  BuildPlan
//
//  Produces the ordered list of changes that turns a wolf template into a
//  player-aligned fighting companion, and reports whether the plan is
//  self-consistent.
// ---------------------------------------------------------------------------
Plan BuildPlan() {
    Plan p;

    // --- 1. faction: the single most important change ----------------------
    // Wolf ships as "WildBeast". Switching to PlayerAlly makes the player's
    // own attacks and the faction's friendly fire rules treat it as an ally,
    // while still letting it attack hostiles.
    p.faction.from = "WildBeast";
    p.faction.to   = "PlayerAlly";
    p.faction.valid = (strcmp(p.faction.to, "Player") == 0 ||
                       strcmp(p.faction.to, "PlayerAlly") == 0);

    // --- 2. IsTame: stops the hostile wildlife behaviour -------------------
    // Adding this component is what disables the "attack the player on sight"
    // branch, per the docstring shipped in the exe.
    p.addIsTame      = true;
    p.isTameMeaning  = "Wildlife behaviour is suppressed once IsTame is present";

    // --- 3. Animal components: persistence + replication -------------------
    p.addAnimal      = true;   // keen::ecs::Animal
    p.addAnimalSaved = true;   // keen::ecs::AnimalSaved  (survives save/load)
    p.addNetworkAnimal= true;  // keen::ecs::NetworkAnimal (replicates in MP)

    // --- 4. combat AI: keep as-is ------------------------------------------
    // The wolf already carries the whole fighting stack. We must NOT strip
    // these, and we must NOT flip Aggro off the way the tameable base class
    // does (applyEnemyValue: false) — that would make it a passive pet.
    p.keepCombatAI        = true;
    p.keepAggroEnemyValue = true;   // wolf already has this as true

    // --- 5. follow behaviour ----------------------------------------------
    // AdminSpawnCommand.followPlayer is the shipped field; a tamed wolf spawned
    // through it will trail the player. Following does not need custom AI.
    p.followViaSpawnFlag = true;

    // --- 6. the components we must NOT add --------------------------------
    // Base_Companion brings Boss, BossHealthBar, LifeTime and friends. None of
    // those belong on a pet, and LifeTime would make the wolf expire.
    p.avoidComponents.push_back("keen::ecs::LifeTime");
    p.avoidComponents.push_back("keen::ecs::Boss");
    p.avoidComponents.push_back("keen::ecs::BossHealthBar");

    // --- validate ---------------------------------------------------------
    p.valid = p.faction.valid && p.addIsTame && p.addAnimal &&
              p.addAnimalSaved && p.addNetworkAnimal && p.keepCombatAI &&
              p.keepAggroEnemyValue && p.followViaSpawnFlag;

    return p;
}

// ---------------------------------------------------------------------------
//  Describe — for the mod menu
// ---------------------------------------------------------------------------
const char* Describe(const Plan& p) {
    static char buf[256];
    snprintf(buf, sizeof(buf),
             "阵营 %s -> %s | IsTame | Animal/Saved/Network | 保留战斗 AI",
             p.faction.from, p.faction.to);
    return buf;
}

} // namespace wolfmount::follow
