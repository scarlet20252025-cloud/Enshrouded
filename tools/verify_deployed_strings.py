"""Verify the deployed DLL actually contains the strings we log.

Checks the binary for the log lines that must be present after the desc+0x18
fix, so a stale DLL can never masquerade as a fixed one. Byte-level search, no
encoding assumptions.

Usage: python tools/verify_deployed_strings.py [dll_path]

If no path is given, the DLL next to the game's enshrouded.exe is checked, so
this works on a fresh clone with no arguments.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common


def default_dll():
    exe = common.exe_path()
    if not exe:
        return None
    return os.path.join(os.path.dirname(exe), "wolfmount_layer.dll")

# (label, needle) — needle is ASCII, searched as raw bytes.
EXPECT = [
    ("spawn: factory ignores position",
     b"factory ignores position"),
    ("spawn: no entity",
     b"create(guid %02x%02x%02x%02x...) -> "),
    ("move: not yet in manager",
     b"not yet in the manager"),
    ("move: no plausible slot",
     b"outside the plausible range"),
    ("move: slot not writable",
     b"slot %d not writable"),
    ("move: read-back mismatch",
     b"read-back mismatch"),
    ("move: success",
     b"entity %u -> (%.1f, %.1f, %.1f) via slot %d"),
    # The mount wiring. These are the lines that prove the deployed DLL has the
    # entity-backed mount rather than the old state-machine-only version.
    ("mount: attach succeeded",
     b"mounted on entity %u"),
    ("mount: detach",
     b"dismounted from entity %u"),
    ("mount: wolf died while riding",
     b"is no longer live; dropping"),
    ("mount: player inherits the transform",
     b"will inherit its transform"),
    # The old lie must be GONE.
    ("spawn: removed 'at (x, y, z)' claim",
     b"level %u -> entity %u"),
]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else default_dll()
    if not path or not os.path.exists(path):
        print("MISSING %s" % (path or "wolfmount_layer.dll next to the game"))
        return 2
    data = open(path, "rb").read()
    print("%s  (%d bytes)" % (path, len(data)))
    bad = 0
    for label, needle in EXPECT:
        present = needle in data
        want = ("removed" not in label)
        ok = (present == want)
        if not ok:
            bad += 1
        print("  [%s] %-38s %s" % ("ok" if ok else "FAIL",
                                   label,
                                   "present" if present else "absent"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
