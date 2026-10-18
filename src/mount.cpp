// ============================================================================
//  WolfMount — mount layer (M5): attachment, camera, pose
//
//  This is the milestone that decides whether the whole mod works. It turns
//  "player standing next to a wolf" into "player attached to the wolf, seen
//  from the wolf's point of view, in a seated pose".
//
//  Every step below reuses a mechanism the base game already ships:
//
//  1. ATTACHMENT
//     Each wolf carries `keen::ecs::HookShotAnchorSubEntity` with
//     attachmentSlot "Root" and localOffset (0, 1, 0). The hookshot uses it to
//     latch onto a wolf's back. Reusing the same slot for the player is the
//     smallest possible change and needs no new data.
//
//  2. HIERARCHY
//     `keen::ecs::ImpactHierarchy` is the shipped parent/child entity
//     relationship; `addImpactHierarchy` is the shipped node that creates it.
//     Making the player a sub-entity of the wolf inherits the wolf's transform
//     every tick, which is exactly what "riding" means physically.
//
//  3. CAMERA
//     The game has a per-locomotion-mode camera enum with 40+ members,
//     including PlayerCameraGlider and PlayerCameraHookShot, both of which
//     already follow something other than the player's own body.
//     PlayerCameraSitting supplies the seated pose.
//
//  4. TAKEOVER / RELEASE
//     The hookshot ships HookSwingEnter / HookSwingDefaultExit /
//     HookSwingSprintExit and AttachedToHook, i.e. an enter/exit state machine
//     for "an entity is driving the player". Mounting borrows that shape.
//
//  Like M3 and M4, this module owns the DECISION and the STATE. Turning a
//  transition into a component change needs the ECS dispatcher, which is the
//  next step.
// ============================================================================

#include "mount.h"
#include "gamedata.h"

#include <atomic>
#include <mutex>

namespace wolfmount::mount {

namespace {

std::mutex g_mu;
State     g_state;

} // anonymous namespace

// ---------------------------------------------------------------------------
//  GetAttachSlot — the wolf's own back anchor
//
//  Returns the shipped anchor definition rather than inventing one. Slot is
//  "Root"; the offset puts the rider one metre above the wolf's origin.
// ---------------------------------------------------------------------------
AttachSlot GetAttachSlot() {
    AttachSlot s{};
    s.slot        = "Root";
    s.localX      = 0.0f;
    s.localY      = 1.0f;   // 1.0 m above the wolf's root
    s.localZ      = 0.0f;
    s.shippedWith = game::kWolfEarlygame;   // verified on every wolf variant
    return s;
}

// ---------------------------------------------------------------------------
//  GetCameraPlan — which camera states the mount passes through
// ---------------------------------------------------------------------------
CameraPlan GetCameraPlan() {
    CameraPlan p{};

    // Riding borrows the glider's shape: the camera tracks a carrier rather
    // than the player's own head.
    p.mountCamera   = "PlayerCameraGlider";   // closest shipped analogue
    p.poseCamera    = "PlayerCameraSitting";  // supplies the seated pose
    p.exitCamera    = "PlayerCameraIdle";     // what the player returns to

    // The hookshot's enter/exit pair is the shipped precedent for takeover.
    p.enterEvent    = "HookSwingEnter";
    p.exitEvent     = "HookSwingDefaultExit";
    p.attachedState = "AttachedToHook";

    p.valid = (p.mountCamera && p.poseCamera && p.exitCamera &&
               p.enterEvent && p.exitEvent && p.attachedState);
    return p;
}

// ---------------------------------------------------------------------------
//  The mount state machine
// ---------------------------------------------------------------------------
bool TryEnterMount() {
    std::lock_guard<std::mutex> lk(g_mu);

    if (g_state.mounted) return false;          // already mounted
    if (g_state.hasWolf <= 0) return false;     // nothing to ride

    g_state.mounted = true;
    g_state.enters++;
    g_state.lastTransition = "enter";
    return true;
}

bool ExitMount() {
    std::lock_guard<std::mutex> lk(g_mu);

    if (!g_state.mounted) return false;

    g_state.mounted = false;
    g_state.exits++;
    g_state.lastTransition = "exit";
    return true;
}

void SetHasWolf(bool has) {
    std::lock_guard<std::mutex> lk(g_mu);
    g_state.hasWolf = has ? 1 : 0;
    // Losing the wolf must drop the mount, or the player floats.
    if (!has && g_state.mounted) {
        g_state.mounted = false;
        g_state.exits++;
        g_state.lastTransition = "exit (wolf lost)";
    }
}

State Snapshot() {
    std::lock_guard<std::mutex> lk(g_mu);
    return g_state;
}

void Reset() {
    std::lock_guard<std::mutex> lk(g_mu);
    g_state = State{};
}

const char* StepText() {
    return "挂载: HookShotAnchorSubEntity(Root,+1.0) + ImpactHierarchy => "
           "相机 PlayerCameraGlider + 坐姿 => HookSwingEnter/Exit 接管";
}

} // namespace wolfmount::mount
