// ============================================================================
//  WolfMount — faction relation tests
//
//  These pin the hostility table against the game's own machine code. The
//  reference function lives at RVA 0xE892F0 in the shipped image; the tables
//  here are transcribed from its disassembly, so a divergence means either the
//  transcription drifted or the game changed. Either way we want to know.
//
//  Deliberately free of Windows headers: IsEnemy/IsFriend are pure functions,
//  which is exactly why they are worth testing at all.
// ============================================================================

#include "faction.h"

#include <cstdio>
#include <cstdint>

using namespace wolfmount::faction;

namespace {

int g_failures = 0;

void Check(bool cond, const char* what) {
    if (cond) return;
    ++g_failures;
    printf("FAIL: %s\n", what);
}

void CheckEq(int got, int want, const char* what) {
    if (got == want) return;
    ++g_failures;
    printf("FAIL: %s (got %d, want %d)\n", what, got, want);
}

// --- the enum itself -------------------------------------------------------
void TestEnumValues() {
    CheckEq(Environment, 0, "Environment == 0");
    CheckEq(HitAll, 1, "HitAll == 1");
    CheckEq(Fogger, 2, "Fogger == 2");
    CheckEq(Vukah, 3, "Vukah == 3");
    CheckEq(Scavenger, 4, "Scavenger == 4");
    CheckEq(Wildlife, 5, "Wildlife == 5");
    CheckEq(WildBeast, 6, "WildBeast == 6");
    CheckEq(Player, 7, "Player == 7");
    CheckEq(AutomatedPlayer, 8, "AutomatedPlayer == 8");
    CheckEq(HitOthers, 9, "HitOthers == 9");
    CheckEq(Skeleton, 10, "Skeleton == 10");
    CheckEq(PlayerAlly, 11, "PlayerAlly == 11");
    CheckEq(FarmAnimal, 12, "FarmAnimal == 12");
    CheckEq(Cyclops, 13, "Cyclops == 13");
    CheckEq(Drak, 14, "Drak == 14");
    CheckEq(Ancients, 15, "Ancients == 15");
    CheckEq(kPlayer, 7, "kPlayer");
    CheckEq(kPlayerAlly, 11, "kPlayerAlly");
}

// --- the rules that the mod actually depends on ----------------------------
void TestWolfHostility() {
    // A wild wolf is dangerous to the player. This is the "before" state.
    Check(IsEnemy(WildBeast, Player), "wild wolf is hostile to the player");
    Check(IsEnemy(Player, WildBeast), "player is hostile to a wild wolf");

    // The whole point of the mod: after the faction write, the wolf is an ally.
    Check(!IsEnemy(PlayerAlly, Player), "PlayerAlly is NOT hostile to the player");
    Check(!IsEnemy(Player, PlayerAlly), "player is NOT hostile to PlayerAlly");

    // ...but it still fights the things a wolf fights. The ally does not become
    // a pacifist, and it does not turn on wildlife it used to hunt.
    Check(IsEnemy(PlayerAlly, Skeleton), "PlayerAlly still fights skeletons");
    Check(IsEnemy(PlayerAlly, Vukah), "PlayerAlly still fights Vukah");
    Check(IsEnemy(PlayerAlly, Scavenger), "PlayerAlly still fights scavengers");
    Check(IsEnemy(PlayerAlly, Wildlife), "PlayerAlly still fights wildlife");
    Check(IsEnemy(PlayerAlly, FarmAnimal), "PlayerAlly still fights farm animals");
    Check(!IsEnemy(PlayerAlly, Player), "PlayerAlly does not fight the player");
    Check(!IsEnemy(PlayerAlly, AutomatedPlayer), "PlayerAlly does not fight NPC allies");
    Check(!IsEnemy(PlayerAlly, PlayerAlly), "PlayerAlly does not fight other allies");

    // This is the shortcut the menu uses to answer "is the wolf tame?".
    Check(WolfHostileToPlayer(WildBeast), "WolfHostileToPlayer(WildBeast)");
    Check(!WolfHostileToPlayer(PlayerAlly), "WolfHostileToPlayer(PlayerAlly)");
    // Wildlife (5) also lands in `b != Cyclops`, so the raw rule says a
    // Wildlife-faction entity is hostile to the player too. The game keeps farm
    // animals peaceful by giving them FarmAnimal/Animal components and a
    // different faction, not by this table. Pin the raw answer so nobody
    // "simplifies" it later.
    Check(WolfHostileToPlayer(Wildlife), "Wildlife row: hostile to everything but Cyclops");
}

void TestEnvironmentAndHitAll() {
    // Environment never initiates a fight; HitAll attacks every faction
    // INCLUDING Environment — the `a == 0` guard tests `a`, not `b`, so there is
    // no exemption on the receiving side.
    for (int b = 0; b < 16; ++b) {
        Check(!IsEnemy(Environment, (uint8_t)b), "Environment is passive");
        Check(IsEnemy(HitAll, (uint8_t)b), "HitAll attacks every faction");
    }
    // Symmetry is NOT a property of this table, and callers must not assume it.
    Check(IsEnemy(HitAll, Player), "HitAll attacks the player");
    Check(IsEnemy(Player, HitAll), "player attacks HitAll too");
}

void TestSameFaction() {
    // Same faction never fights itself — except HitAll, handled above, and the
    // player group, which is handled by IsPlayerGroup.
    for (int a = 2; a < 16; ++a) {
        if (a == HitAll) continue;
        Check(!IsEnemy((uint8_t)a, (uint8_t)a), "same faction is not hostile");
    }
}

void TestSpecificPairs() {
    // A handful of pairs that are easy to get backwards, each taken from the
    // game's own branch structure.
    Check(IsEnemy(Vukah, Skeleton), "Vukah attacks skeletons");
    Check(!IsEnemy(Vukah, WildBeast), "Vukah leaves wolves alone");
    Check(!IsEnemy(WildBeast, Vukah), "wolf leaves Vukah alone");
    Check(!IsEnemy(WildBeast, Skeleton), "wolf leaves skeletons alone");
    Check(!IsEnemy(WildBeast, Cyclops), "wolf leaves cyclopes alone");
    Check(!IsEnemy(WildBeast, Drak), "wolf leaves Draks alone");
    Check(IsEnemy(WildBeast, Scavenger), "wolf attacks scavengers");
    Check(IsEnemy(WildBeast, Wildlife), "wolf attacks wildlife (why we could not tell)");
    Check(IsEnemy(WildBeast, FarmAnimal), "wolf attacks farm animals");
    Check(!IsEnemy(Skeleton, WildBeast), "skeleton leaves wolves alone");
    Check(!IsEnemy(Skeleton, Fogger), "skeleton leaves foggers alone");
    Check(IsEnemy(Skeleton, Player), "skeleton attacks the player");
    Check(!IsEnemy(Fogger, Skeleton) , "fogger leaves skeletons alone");
    Check(!IsEnemy(Cyclops, Wildlife), "cyclops leaves wildlife alone");
    Check(!IsEnemy(Cyclops, WildBeast), "cyclops leaves wolves alone");
    Check(IsEnemy(Cyclops, Player), "cyclops attacks the player");
    Check(!IsEnemy(Wildlife, Cyclops), "wildlife leaves cyclopes alone");
    // Wildlife's rule is `b != Cyclops`, so it IS hostile to the player on the
    // raw table. What actually keeps farm animals peaceful is that they carry
    // the Animal/Wildlife component set and a FarmAnimal faction; this function
    // only answers the faction question.
    Check(IsEnemy(Wildlife, Player), "wildlife row is hostile to the player");
    Check(!IsEnemy(Drak, WildBeast), "Drak leaves wolves alone");
    Check(IsEnemy(Drak, Player), "Drak attacks the player");
}

void TestFriend() {
    Check(IsFriend(Player, PlayerAlly), "player and ally are friends");
    Check(IsFriend(PlayerAlly, Player), "ally and player are friends");
    Check(IsFriend(WildBeast, WildBeast), "same faction is friendly");
    Check(!IsFriend(WildBeast, Player), "wolf and player are not friends");
    Check(!IsFriend(Player, WildBeast), "player and wolf are not friends");

    // Friend and enemy are NOT complements: two neutral factions can be
    // neither. Callers that treat !IsFriend as "enemy" would be wrong.
    const bool f = IsFriend(Scavenger, Wildlife);
    const bool e = IsEnemy(Scavenger, Wildlife);
    Check(!f && e, "scavenger vs wildlife: enemy but not friend");
}

void TestPlayerGroup() {
    Check(IsPlayerGroup(Player), "Player is in the group");
    Check(IsPlayerGroup(AutomatedPlayer), "AutomatedPlayer is in the group");
    Check(IsPlayerGroup(PlayerAlly), "PlayerAlly is in the group");
    Check(!IsPlayerGroup(WildBeast), "WildBeast is not in the group");
    Check(!IsPlayerGroup(Environment), "Environment is not in the group");

    // The group is fully mutually friendly in both directions.
    const uint8_t group[] = {Player, AutomatedPlayer, PlayerAlly};
    for (uint8_t a : group) {
        for (uint8_t b : group) {
            Check(!IsEnemy(a, b), "player group is mutually non-hostile");
            Check(IsFriend(a, b), "player group is mutually friendly");
        }
    }
}

void TestExhaustiveSanity() {
    // Every pair must answer, and the answers must be self-consistent where the
    // engine guarantees it: nothing in the player group attacks anything.
    int hostilePairs = 0;
    for (int a = 0; a < 256; ++a) {
        for (int b = 0; b < 256; ++b) {
            const bool e = IsEnemy((uint8_t)a, (uint8_t)b);
            if (e) ++hostilePairs;
            if (a == Environment) Check(!e, "Environment row is all false");
            if (a != 0 && b != 0 && a == b && a > 1) {
                Check(!e, "diagonal is false above HitAll");
            }
            if (IsPlayerGroup((uint8_t)a) && IsPlayerGroup((uint8_t)b)) {
                Check(!e, "player group box is all false");
            }
        }
    }
    // 16x16 = 256 canonical pairs; the table is 8-bit tolerant though, so the
    // count for the full 256x256 sweep is pinned only as "some, not all".
    Check(hostilePairs > 0, "some pairs are hostile");
    Check(hostilePairs < 256 * 256, "not every pair is hostile");
    printf("     hostile pairs in full 256x256 sweep: %d\n", hostilePairs);
}

// The 16x16 canonical table, printed so a reviewer can eyeball it against the
// disassembly without running anything.
void PrintTable() {
    static const char* names[16] = {
        "Env", "HitAll", "Fog", "Vukah", "Scav", "Wild", "WBeast", "Player",
        "AutoP", "HitOth", "Skel", "Ally", "Farm", "Cycl", "Drak", "Anc",
    };
    printf("\n     isEnemy(a, b) — rows are a, columns are b\n     %-7s", "");
    for (int b = 0; b < 16; ++b) printf("%-4d", b);
    printf("\n");
    for (int a = 0; a < 16; ++a) {
        printf("     %-7s", names[a]);
        for (int b = 0; b < 16; ++b) printf("%-4d", IsEnemy((uint8_t)a, (uint8_t)b) ? 1 : 0);
        printf("\n");
    }
}

} // namespace

int main() {
    printf("faction relation tests\n");
    TestEnumValues();
    TestWolfHostility();
    TestEnvironmentAndHitAll();
    TestSameFaction();
    TestSpecificPairs();
    TestFriend();
    TestPlayerGroup();
    TestExhaustiveSanity();
    PrintTable();

    if (g_failures == 0) {
        printf("\nRESULT: PASS\n");
        return 0;
    }
    printf("\nRESULT: FAIL (%d)\n", g_failures);
    return 1;
}
