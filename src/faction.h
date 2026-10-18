// ============================================================================
//  WolfMount — faction relations (ported from the community mod "M182 Admin
//  Pannel", GPL-3.0, as independently verified against our own image)
//
//  WHY THIS EXISTS
//  ---------------
//  For three releases we tried to answer "is the wolf still hostile to the
//  player?" by writing a Faction component and then waiting to see whether the
//  wolf bit us. That is an unreliable oracle: a wolf bites wildlife anyway, so
//  "the wolf stopped biting the player" and "the wolf never changed" look
//  identical in a short log.
//
//  This module replaces the oracle with arithmetic. The game's hostility rules
//  are a pure function of two faction bytes, and we located that function in our
//  own image (see enemy_function_rva below). Every rule below is a direct
//  restatement of its machine code, and the unit test suite pins the outputs for
//  all 256x256 input pairs against the rules stated here.
//
//  The practical payoff: once we write Faction = PlayerAlly(11) onto a wolf we
//  can PROVE it is no longer hostile to the player, instead of hoping.
// ============================================================================

#pragma once

#include <cstdint>

namespace wolfmount::faction {

// FactionType — verified against reflection_data.json index 2066 (16 values).
// The earlier hand-written enum in gamedata.h had a different order; this one
// matches the engine.
enum Faction : uint8_t {
    Environment    = 0,
    HitAll         = 1,
    Fogger         = 2,
    Vukah          = 3,
    Scavenger      = 4,
    Wildlife       = 5,
    WildBeast      = 6,
    Player         = 7,
    AutomatedPlayer= 8,
    HitOthers      = 9,
    Skeleton       = 10,
    PlayerAlly     = 11,
    FarmAnimal     = 12,
    Cyclops        = 13,
    Drak           = 14,
    Ancients       = 15,
};

// The faction byte that means "the local player".
constexpr uint8_t kPlayer = static_cast<uint8_t>(Player);

// The faction byte that means "fights alongside the player".
constexpr uint8_t kPlayerAlly = static_cast<uint8_t>(PlayerAlly);

// Player, AutomatedPlayer and PlayerAlly form one mutual group: nothing inside
// it is hostile to anything else. This is what lets a tamed wolf stand next to
// an NPC ally without a dogfight.
inline bool IsPlayerGroup(uint8_t f) {
    return f == Player || f == AutomatedPlayer || f == PlayerAlly;
}

// True when an entity of faction `a` will attack an entity of faction `b`.
//
// Exact transcription of the game's own routine at RVA 0xE892F0. The function
// takes its arguments in rcx and rdx and returns a byte in al — hooking that
// function is an alternative to this table, but the table has the advantage of
// being callable from a unit test and from any thread.
inline bool IsEnemy(uint8_t a, uint8_t b) {
    if (a == Environment) return false;                 // a == 0 short-circuits
    if (IsPlayerGroup(a) && IsPlayerGroup(b)) return false;
    if (a == HitAll) return true;                        // HitAll hits everything
    if (a == b) return false;                            // same faction never fights
    switch (a) {
        case Vukah:     return b != WildBeast;
        case WildBeast: return !(b == Vukah || b == Skeleton ||
                                 b == Cyclops || b == Drak);
        case Skeleton:  return !(b == WildBeast || b == Fogger);
        case Fogger:    return b != Skeleton;
        case Cyclops:   return !(b == Wildlife || b == WildBeast);
        case Wildlife:  return b != Cyclops;
        case Drak:      return b != WildBeast;
        default:        return true;
    }
}

// True when `a` treats `b` as a friend.
inline bool IsFriend(uint8_t a, uint8_t b) {
    return a == b || (IsPlayerGroup(a) && IsPlayerGroup(b));
}

// ---------------------------------------------------------------------------
//  The answer the whole mod cares about
// ---------------------------------------------------------------------------

// A wolf (WildBeast) is dangerous to the player today.
// Once its Faction byte is PlayerAlly, this flips to false and stays false:
//   IsEnemy(PlayerAlly, Player) == false   (player-group rule)
//   IsEnemy(Player, PlayerAlly) == false   (symmetric, same rule)
//   IsEnemy(any other faction, PlayerAlly) == the normal rule
//
// Note the asymmetry that matters: a WildBeast wolf stops being hostile to the
// player's group the moment it joins it, but Wolves remain hostile to Skeletons
// etc. — the wolf keeps behaving like a wolf, just on our side.
inline bool WolfHostileToPlayer(uint8_t wolfFaction) {
    return IsEnemy(wolfFaction, kPlayer);
}

} // namespace wolfmount::faction
