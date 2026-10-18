import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()

    # The ENQ cap was reverted to 5000 (never sampled) because the earlier
    # sample patch targeted a differently-formatted block. That is what stalled
    # the game again: 5k lines of fopen/fprintf on the game thread.
    old = """    int n = g_enqueueCount.fetch_add(1, std::memory_order_relaxed) + 1;
        if (n <= 5000) {     WM_MOD_LOG("[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u",
                   n, ctx, entityId, size, (unsigned)flags);
    }"""
    new = """    int n = g_enqueueCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 200 || (n % 200) == 0) {
        WM_MOD_LOG("[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u",
                   n, ctx, entityId, size, (unsigned)flags);
    }"""
    if old not in s:
        print("ENQ block not found in the expected shape — inspect manually")
        return
    s = s.replace(old, new, 1)

    # Same for SEND: it was capped at 60, which is fine, but make it sampled in
    # case the hot UI queue sustains a high rate.
    old2 = """    static std::atomic<int> s_sendCount{0};
    const int n = s_sendCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 60) {"""
    new2 = """    static std::atomic<int> s_sendCount{0};
    const int n = s_sendCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 60 || (n % 200) == 0) {"""
    if old2 in s:
        s = s.replace(old2, new2, 1)
        print("sampled SEND too")

    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("ENQ trace sampled (first 200 + every 200th)")


if __name__ == "__main__":
    main()
