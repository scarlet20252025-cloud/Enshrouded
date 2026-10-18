// ===========================================================================
//  gamehooks-stub.cpp — link stubs for head-less entityops tests
//
//  entityops.cpp links against the game-hook layer for two pointers
//  (WorldContext, WorldHolder). A unit test must not pull in gamehooks.cpp --
//  that file detours live game code -- so satisfy the two symbols here with
//  values meaning "no world yet". Nothing under test reaches them.
// ===========================================================================

namespace wolfmount::gamehooks {

void* WorldContext() { return nullptr; }
void* WorldHolder() { return nullptr; }

} // namespace wolfmount::gamehooks
