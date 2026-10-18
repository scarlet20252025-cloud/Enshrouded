#pragma once
// ============================================================================
//  WolfMount — mount layer (M5)
//
//  Attachment / camera / pose for riding the wolf. Every mechanism named here
//  already exists in the shipped game; see mount.cpp for the evidence.
// ============================================================================

#include <cstdint>

namespace wolfmount::mount {

// The wolf's shipped back anchor.
struct AttachSlot {
    const char* slot = "";        // "Root"
    float localX = 0.0f;
    float localY = 0.0f;          // 1.0 m above the wolf's origin
    float localZ = 0.0f;
    const char* shippedWith = ""; // which template it was verified on
};

// The wolf's shipped back anchor. Named GetAttachSlot to avoid colliding with
// the AttachSlot struct name.
AttachSlot GetAttachSlot();

// Camera and takeover plan.
struct CameraPlan {
    const char* mountCamera = "";    // camera while riding
    const char* poseCamera = "";     // supplies the seated pose
    const char* exitCamera = "";     // camera after dismounting
    const char* enterEvent = "";     // takeover event
    const char* exitEvent = "";      // release event
    const char* attachedState = "";  // the "is attached" state
    bool valid = false;
};

// Camera and takeover plan. Named GetCameraPlan to avoid colliding with the
// CameraPlan struct name.
CameraPlan GetCameraPlan();

// Observable mount state.
struct State {
    bool mounted = false;
    int  hasWolf = 0;
    int  enters = 0;
    int  exits = 0;
    const char* lastTransition = "none";
};

bool TryEnterMount();
bool ExitMount();
void SetHasWolf(bool has);
State Snapshot();
void Reset();

const char* StepText();

} // namespace wolfmount::mount
