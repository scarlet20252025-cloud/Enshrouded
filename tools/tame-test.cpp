// ============================================================================
//  WolfMount — taming rules unit test
//
//  Exercises every rule in src\tame.cpp using the GUIDs and itemIds extracted
//  from the shipped 1.0 game data. No game required.
//
//  Rules under test:
//    1. wolf + torch          -> ConvertToTame
//    2. non-wolf + torch      -> Ignore
//    3. wolf + non-torch      -> Ignore
//    4. second wolf + torch   -> Ignore (only one may be tamed)
// ============================================================================

#include "gamedata.h"
#include "tame.h"

#include <cstdio>
#include <cstring>

using namespace wolfmount;

static int g_fail = 0;

static void Check(bool ok, const char* what) {
    if (ok) {
        printf("  PASS  %s\n", what);
    } else {
        printf("  FAIL  %s\n", what);
        g_fail++;
    }
}

int main() {
    printf("=== WolfMount taming rules test ===\n\n");

    // --- data sanity --------------------------------------------------------
    printf("[data]\n");
    Check(game::IsTorch(game::kTorches[0].itemId), "Tool_Torch01 recognised as torch");
    Check(game::IsTorch(game::kTorches[1].itemId), "Tool_Torch02 recognised as torch");
    Check(game::IsTorch(game::kTorches[2].itemId), "Tool_Torch03 recognised as torch");
    Check(game::IsTorch(game::kTorches[3].itemId), "Tool_Torch04 recognised as torch");
    Check(!game::IsTorch(0), "itemId 0 is not a torch");
    Check(!game::IsTorch(1), "itemId 1 is not a torch");

    Check(wolfmount::tame::IsWolfTemplate(game::kWolfEarlygame), "earlygame wolf recognised");
    Check(wolfmount::tame::IsWolfTemplate(game::kWolfHeavy), "heavy wolf recognised");
    Check(!wolfmount::tame::IsWolfTemplate(game::kDogBright), "dog is not a wolf");
    Check(!wolfmount::tame::IsWolfTemplate(nullptr), "null template is not a wolf");
    printf("\n");

    // --- rule 1: wolf + torch ----------------------------------------------
    printf("[rule 1] wolf killed with a torch -> tame\n");
    wolfmount::tame::Reset();
    {
        wolfmount::tame::KillEvent ev;
        ev.victimTemplateGuid = game::kWolfEarlygame;
        ev.weaponItemId       = game::kTorches[0].itemId;

        auto d = wolfmount::tame::OnEntityKilled(ev);
        Check(d.action == wolfmount::tame::Action::ConvertToTame, "action is ConvertToTame");
        Check(d.wasWolf, "decision reports wasWolf");
        Check(d.wasTorch, "decision reports wasTorch");
        Check(!d.alreadyOwned, "not already owned at this point");

        auto s = wolfmount::tame::Snapshot();
        Check(s.tamedCount == 1, "tamedCount is 1");
        Check(s.convertedKills == 1, "convertedKills is 1");
        Check(s.tamedGuid != nullptr, "tamedGuid recorded");
    }
    printf("\n");

    // --- rule 2: non-wolf + torch ------------------------------------------
    printf("[rule 2] non-wolf killed with a torch -> ignore\n");
    {
        wolfmount::tame::KillEvent ev;
        ev.victimTemplateGuid = game::kDogBright;   // a dog, not a wolf
        ev.weaponItemId       = game::kTorches[1].itemId;

        auto d = wolfmount::tame::OnEntityKilled(ev);
        Check(d.action == wolfmount::tame::Action::Ignore, "action is Ignore");
        Check(!d.wasWolf, "victim correctly identified as not a wolf");
        Check(d.wasTorch, "weapon correctly identified as torch");

        auto s = wolfmount::tame::Snapshot();
        Check(s.tamedCount == 1, "tamedCount still 1 (unchanged)");
        Check(s.convertedKills == 1, "convertedKills still 1");
    }
    printf("\n");

    // --- rule 3: wolf + non-torch ------------------------------------------
    printf("[rule 3] wolf killed without a torch -> ignore\n");
    {
        wolfmount::tame::Reset();
        wolfmount::tame::KillEvent ev;
        ev.victimTemplateGuid = game::kWolfHeavy;
        ev.weaponItemId       = 12345;              // some non-torch weapon

        auto d = wolfmount::tame::OnEntityKilled(ev);
        Check(d.action == wolfmount::tame::Action::Ignore, "action is Ignore");
        Check(d.wasWolf, "victim is a wolf");
        Check(!d.wasTorch, "weapon is not a torch");

        auto s = wolfmount::tame::Snapshot();
        Check(s.tamedCount == 0, "nothing tamed");
        Check(s.wolfKillsWithoutTorch == 1, "wolf kill without torch counted");
    }
    printf("\n");

    // --- rule 4: second wolf + torch ---------------------------------------
    printf("[rule 4] second wolf + torch after one is owned -> ignore\n");
    {
        wolfmount::tame::Reset();

        wolfmount::tame::KillEvent first;
        first.victimTemplateGuid = game::kWolfEarlygame;
        first.weaponItemId       = game::kTorches[0].itemId;
        auto d1 = wolfmount::tame::OnEntityKilled(first);
        Check(d1.action == wolfmount::tame::Action::ConvertToTame, "first kill tames");

        wolfmount::tame::KillEvent second;
        second.victimTemplateGuid = game::kWolfHeavy;
        second.weaponItemId       = game::kTorches[0].itemId;
        auto d2 = wolfmount::tame::OnEntityKilled(second);
        Check(d2.action == wolfmount::tame::Action::Ignore, "second kill is ignored");
        Check(d2.alreadyOwned, "decision reports already owned");

        wolfmount::tame::KillEvent third;
        third.victimTemplateGuid = game::kWolfAutoTest;
        third.weaponItemId       = game::kTorches[2].itemId;
        auto d3 = wolfmount::tame::OnEntityKilled(third);
        Check(d3.action == wolfmount::tame::Action::Ignore, "third kill also ignored");

        auto s = wolfmount::tame::Snapshot();
        Check(s.tamedCount == 1, "still exactly one tamed");
        Check(s.convertedKills == 1, "only one conversion happened");
        Check(s.ignoredKills == 2, "two kills were ignored");

        // The FIRST wolf stays the tamed one.
        Check(s.tamedGuid != nullptr &&
              strcmp(s.tamedGuid, game::kWolfEarlygame) == 0,
              "the first wolf remains the tamed one");
    }
    printf("\n");

    // --- all wolf variants tame the same way ------------------------------
    printf("[coverage] every wolf template can be tamed\n");
    {
        const char* wolves[] = { game::kWolfEarlygame, game::kWolfHeavy,
                                 game::kWolfAutoTest, game::kWolfHookAG2,
                                 game::kWolfBossHeavy };
        for (auto* w : wolves) {
            wolfmount::tame::Reset();
            wolfmount::tame::KillEvent ev;
            ev.victimTemplateGuid = w;
            ev.weaponItemId       = game::kTorches[3].itemId;  // underwater torch
            auto d = wolfmount::tame::OnEntityKilled(ev);
            printf("       %s -> %s\n", w,
                   d.action == wolfmount::tame::Action::ConvertToTame ? "tamed" : "ignored");
            Check(d.action == wolfmount::tame::Action::ConvertToTame,
                  "wolf variant tames with a torch");
        }
    }

    printf("\n");
    if (g_fail == 0) {
        printf("RESULT: PASS — all taming rules behave correctly\n");
        return 0;
    }
    printf("RESULT: FAIL — %d check(s) failed\n", g_fail);
    return 1;
}
