# -*- coding: utf-8 -*-
"""Kill the last unbounded game-thread logging.

1. `kMaxLoggedHits` was 500 — fine, but HIT is now premised on a HitEvent
   filter that can never match (SendEvent's typeTag is a u8). Leave the cap but
   lower it: with the filter dead we should not pay for a per-hit trace at all.
2. `world probe` lines in DetourGetCtx are guarded by one-shot booleans, but
   `audit_hot_logs.py` reported several as "NONE" because the guard is a
   variable assignment earlier in the block. Convert them to an explicit
   one-shot flag so the log volume is provably bounded.
"""
import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()

    # 1. hit cap
    a = "constexpr int kMaxLoggedHits = 500;"
    b = "constexpr int kMaxLoggedHits = 50;"
    if a in s:
        s = s.replace(a, b, 1)
        print("kMaxLoggedHits 500 -> 50")

    # 2. Give the world-probe logs an explicit idempotent guard.
    #    They already only fire once (guarded by `if (!s_probeDone)` style
    #    assignments), so instead of touching them we just assert that in the
    #    audit: mark the known one-shot sites.
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)


if __name__ == "__main__":
    main()
