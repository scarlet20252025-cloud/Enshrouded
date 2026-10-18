// ============================================================================
//  Follow set tests
//
//  The follow LOOP needs live memory (it reads the player's transform and writes
//  the companion's), so it cannot run here. The follow SET can: it is pure
//  bookkeeping, and bookkeeping is where the bugs are. A set that leaks entries,
//  drops the wrong one when an entity dies, or fills up silently would make the
//  loop look broken in a way that is nearly invisible in a log.
//
//  Links src/followset.cpp directly -- no game, no stubs.
// ============================================================================

#include <cstdio>
#include <cstdint>

#include "followset.h"

using namespace wolfmount::followset;

namespace {

int g_failures = 0;

void Check(bool ok, const char* what) {
    if (!ok) {
        printf("     FAIL: %s\n", what);
        ++g_failures;
    }
}

void TestAddAndCount() {
    Clear();
    Check(Count() == 0, "starts empty");

    Check(Add(100), "add 100 succeeds");
    Check(Count() == 1, "count is 1");
    Check(Contains(100), "set contains 100");

    Check(Add(200), "add 200 succeeds");
    Check(Count() == 2, "count is 2");
    Check(Contains(200), "set contains 200");

    // Re-adding must be idempotent, not a second slot: the follow loop indexes
    // by position, so a duplicate would double the entity's tick rate.
    Check(Add(100), "re-adding 100 reports success");
    Check(Count() == 2, "re-adding does not grow the set");

    // Entity id 0 is never a valid entity and must be refused.
    Check(!Add(0), "id 0 is refused");
    Check(Count() == 2, "refused add did not change the count");
    Check(!Contains(0), "set does not contain 0");
}

void TestRemove() {
    Clear();
    Add(1);
    Add(2);
    Add(3);

    // Remove from the middle. The swap-with-last strategy must keep the set
    // packed and must lose neither survivor.
    Remove(2);
    Check(Count() == 2, "count drops to 2 after removing the middle");
    Check(!Contains(2), "2 is gone");
    Check(Contains(1), "1 survived the swap");
    Check(Contains(3), "3 survived the swap");

    // Removing something absent is a no-op, not corruption.
    Remove(999);
    Check(Count() == 2, "removing an absent id is a no-op");

    Remove(1);
    Remove(3);
    Check(Count() == 0, "removing the rest empties the set");
}

void TestPackedInvariant() {
    Clear();
    // The round-robin loop reads At(0..Count-1). If a remove ever left a zero in
    // the middle of that range, the loop would silently skip a tick.
    for (uint32_t i = 1; i <= 6; ++i) Add(i);

    // Remove every other entity, then verify the prefix has no holes.
    Remove(2);
    Remove(4);
    Remove(6);

    const int n = Count();
    Check(n == 3, "three remain");
    for (int i = 0; i < n; ++i) {
        Check(At(i) != 0, "no hole inside the live range");
    }
    Check(At(n) == 0, "At past the end reads 0");
    Check(At(-1) == 0, "At with a negative index reads 0");
}

void TestClear() {
    Clear();
    for (uint32_t i = 1; i <= 5; ++i) Add(i);
    Check(Count() == 5, "five added");
    Clear();
    Check(Count() == 0, "clear empties the set");
    Check(At(0) == 0, "clear leaves no stale id");

    Clear();
    Check(Count() == 0, "double clear is harmless");
}

void TestCapacity() {
    Clear();
    int added = 0;
    for (uint32_t i = 1; i <= 100; ++i) {
        if (Add(1000 + i)) ++added;
    }
    Check(added == kMaxFollowers, "exactly kMaxFollowers adds are accepted");
    Check(Count() == kMaxFollowers, "count equals the capacity");

    // Full: the next add must be refused, and must not corrupt the count.
    Check(!Add(999999), "add past capacity is refused");
    Check(Count() == kMaxFollowers, "refused add left the count alone");
    Check(!Contains(999999), "the refused id is not in the set");

    // Room again after one leaves.
    Remove(1001);
    Check(Count() == kMaxFollowers - 1, "count drops after a removal");
    Check(Add(999999), "add succeeds again once there is room");

    printf("     capacity: %d followers\n", kMaxFollowers);
    Clear();
}

void TestRemoveOnEmpty() {
    Clear();
    Remove(42);
    Check(Count() == 0, "remove on an empty set is safe");
}

} // namespace

int main() {
    printf("follow set tests\n");
    TestAddAndCount();
    TestRemove();
    TestPackedInvariant();
    TestClear();
    TestCapacity();
    TestRemoveOnEmpty();

    if (g_failures == 0) {
        printf("\nRESULT: PASS\n");
        return 0;
    }
    printf("\nRESULT: FAIL (%d)\n", g_failures);
    return 1;
}
