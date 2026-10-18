# -*- coding: utf-8 -*-
"""Verify that no unbounded fprintf remains on the game thread.

Any WM_MOD_LOG inside DetourEnqueue / DetourSendEvent / FlushPendingComp runs on
the game thread while it is writing components. Every one of them costs an
fprintf+fflush. This script reports each call site's guard so we can prove the
log volume is bounded before deploying.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import io
import re

SRC = os.path.join(ROOT, "src", "gamehooks.cpp")


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    lines = s.splitlines()

    # locate the hot functions
    hot = []
    for i, ln in enumerate(lines):
        if re.match(r"^\w[\w:<>*& ]*\s+\**\s*(DetourEnqueue|DetourSendEvent|FlushPendingComp)\s*\(", ln):
            hot.append(i)
    print("hot functions start at lines: %s" % [i + 1 for i in hot])

    # find every WM_MOD_LOG in the file and report the nearest enclosing 'if'
    logs = [i for i, ln in enumerate(lines) if "WM_MOD_LOG(" in ln]
    unguarded = []
    for i in logs:
        guard = None
        for j in range(i, max(-1, i - 25), -1):
            m = re.match(r"^\s*if\s*\(", lines[j])
            if m:
                guard = lines[j].strip()
                break
            if lines[j].strip() == "}":
                # left the block without meeting an if
                break
        fname = "?"
        for j in range(i, -1, -1):
            m = re.match(r"^[\w:<>*& ]*\s+(\**?\s*\w+)\s*\(", lines[j])
            if m and ("Detour" in m.group(1) or "Flush" in m.group(1)):
                fname = m.group(1).strip()
                break
        print("L%-5d %-22s guard: %s" % (i + 1, fname, guard or "NONE"))
        if guard is None:
            unguarded.append(i + 1)

    print()
    if unguarded:
        print("UNGUARDED log sites (will log on every call!): %s" % unguarded)
    else:
        print("all log sites inside Detour*/Flush* are guarded")


if __name__ == "__main__":
    main()
