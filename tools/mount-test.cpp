// ============================================================================
//  WolfMount — mount state machine test (M5, the deciding milestone)
//
//  Verifies the enter/exit transitions and every fact the mount relies on.
// ============================================================================

#include "gamedata.h"
#include "mount.h"

#include <cstdio>
#include <cstring>

using namespace wolfmount;

static int g_fail = 0;
static void Check(bool ok, const char* what) {
    if (ok) printf("  PASS  %s\n", what);
    else    { printf("  FAIL  %s\n", what); g_fail++; }
}

int main() {
    printf("=== WolfMount mount state machine test ===\n\n");

    // ---- the shipped anchor -----------------------------------------------
    printf("[attachment]\n");
    auto slot = mount::GetAttachSlot();
    Check(strcmp(slot.slot, "Root") == 0, "uses the shipped 'Root' slot");
    Check(slot.localY > 0.9f && slot.localY < 1.1f, "rider sits 1.0 m above the wolf root");
    Check(slot.localX == 0.0f && slot.localZ == 0.0f,
          "no lateral/forward offset from the shipped anchor");
    Check(strcmp(slot.shippedWith, game::kWolfEarlygame) == 0,
          "anchor verified against a real wolf template");
    printf("  slot=%s offset=(%.1f, %.1f, %.1f)  from %s\n\n",
           slot.slot, slot.localX, slot.localY, slot.localZ, slot.shippedWith);

    // ---- the camera plan --------------------------------------------------
    printf("[camera]\n");
    auto cam = mount::GetCameraPlan();
    Check(cam.valid, "camera plan is complete");
    Check(strcmp(cam.mountCamera, "PlayerCameraGlider") == 0,
          "riding camera is a shipped locomotion camera");
    Check(strcmp(cam.poseCamera, "PlayerCameraSitting") == 0,
          "seated pose comes from PlayerCameraSitting");
    Check(strcmp(cam.enterEvent, "HookSwingEnter") == 0,
          "takeover event is the shipped hookswing enter");
    Check(strcmp(cam.exitEvent, "HookSwingDefaultExit") == 0,
          "release event is the shipped hookswing exit");
    Check(strcmp(cam.attachedState, "AttachedToHook") == 0,
          "attached state is a shipped state");
    printf("\n");

    // ---- transitions ------------------------------------------------------
    printf("[transitions]\n");

    // No wolf: cannot mount.
    mount::Reset();
    Check(!mount::TryEnterMount(), "cannot mount without a wolf");

    // With a wolf: mount once.
    mount::SetHasWolf(true);
    Check(mount::TryEnterMount(), "mounts once a wolf exists");
    Check(mount::TryEnterMount() == false, "cannot double-mount");
    {
        auto s = mount::Snapshot();
        Check(s.mounted, "state reports mounted");
        Check(s.enters == 1, "exactly one enter recorded");
    }

    // Dismount.
    Check(mount::ExitMount(), "dismounts");
    Check(mount::Snapshot().mounted == false, "state reports not mounted");
    Check(mount::ExitMount() == false, "cannot dismount twice");

    // Remount.
    Check(mount::TryEnterMount(), "can remount after dismounting");
    {
        auto s = mount::Snapshot();
        Check(s.enters == 2 && s.exits == 1, "enter/exit counters track correctly");
    }

    // Losing the wolf while mounted must drop the mount.
    mount::SetHasWolf(false);
    {
        auto s = mount::Snapshot();
        Check(!s.mounted, "losing the wolf automatically dismounts");
        Check(s.exits == 2, "the forced dismount is counted");
        printf("  last transition: %s\n", s.lastTransition);
    }
    Check(mount::TryEnterMount() == false, "cannot mount with no wolf again");

    // Reacquire and mount again.
    mount::SetHasWolf(true);
    Check(mount::TryEnterMount(), "mounting works after reacquiring a wolf");
    printf("\n");

    // ---- the mechanisms the mount depends on ------------------------------
    printf("[dependencies]\n");
    Check(strcmp(game::kCompHookAnchorSub, "keen::ecs::HookShotAnchorSubEntity") == 0,
          "attachment component name matches the shipped one");
    Check(strcmp(game::kCompImpactHierarchy, "keen::ecs::ImpactHierarchy") == 0,
          "hierarchy component name matches the shipped one");
    printf("\n");

    // ---- what still needs the dispatcher ----------------------------------
    printf("[remaining work]\n");
    printf("  attachment  : needs ImpactHierarchy add with the player as child\n");
    printf("  camera      : needs CameraId set to PlayerCameraGlider\n");
    printf("  pose        : needs the sitting animation slot applied\n");
    printf("  all of the  : above need the ECS dispatcher address\n");
    printf("                (M6: dynamic analysis under a debugger)\n\n");

    if (g_fail == 0) { printf("RESULT: PASS — M5 framework verified\n"); return 0; }
    printf("RESULT: FAIL — %d check(s) failed\n", g_fail);
    return 1;
}
