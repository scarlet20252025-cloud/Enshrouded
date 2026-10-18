// ============================================================================
//  WolfMount - the follow set (implementation)
//
//  A packed array with swap-remove. Nothing here touches the game, so the whole
//  file is exercised by tools/followset-test.cpp.
// ============================================================================

#include "followset.h"

#include <atomic>
#include <cstdint>

namespace wolfmount::followset {
namespace {

uint32_t g_ids[kMaxFollowers] = {0};
std::atomic<int> g_count{0};

} // namespace

bool Add(uint32_t entityId) {
    if (!entityId) return false;

    const int n = g_count.load(std::memory_order_relaxed);
    for (int i = 0; i < n; ++i) {
        if (g_ids[i] == entityId) return true;   // already following
    }
    if (n >= kMaxFollowers) return false;

    g_ids[n] = entityId;
    g_count.store(n + 1, std::memory_order_relaxed);
    return true;
}

void Remove(uint32_t entityId) {
    const int n = g_count.load(std::memory_order_relaxed);
    for (int i = 0; i < n; ++i) {
        if (g_ids[i] != entityId) continue;
        // Swap the last entry into the hole so the array stays packed: the
        // follow loop round-robins over indices, and a sparse array would make
        // it spin on empty slots.
        g_ids[i] = g_ids[n - 1];
        g_ids[n - 1] = 0;
        g_count.store(n - 1, std::memory_order_relaxed);
        return;
    }
}

void Clear() {
    const int n = g_count.load(std::memory_order_relaxed);
    for (int i = 0; i < n; ++i) g_ids[i] = 0;
    g_count.store(0, std::memory_order_relaxed);
}

int Count() { return g_count.load(std::memory_order_relaxed); }

uint32_t At(int index) {
    const int n = g_count.load(std::memory_order_relaxed);
    if (index < 0 || index >= n) return 0;
    return g_ids[index];
}

bool Contains(uint32_t entityId) {
    if (!entityId) return false;
    const int n = g_count.load(std::memory_order_relaxed);
    for (int i = 0; i < n; ++i) {
        if (g_ids[i] == entityId) return true;
    }
    return false;
}

} // namespace wolfmount::followset
