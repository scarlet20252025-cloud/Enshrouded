#!/usr/bin/env python3
"""Map a template name to the 16-byte template GUID the entity factory wants.

TemplateResource filenames are "<uuid>_<resourceId>_<index>.json" and the
16 bytes the spawn descriptor takes are the raw UUID bytes in printed order --
verified against `1_Player`, whose filename is
c3db66d6-89a5-4a6c-a8e3-d9a1f6009812 and whose baked GUID in entityops.cpp is
exactly those bytes.

Usage:
    python tools/tpl_guid.py Enemy_Wildbeast_wolf_earlygame
    python tools/tpl_guid.py --grep wolf
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL_DIR = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource")


def uuid_bytes_from_path(path):
    stem = os.path.basename(path)
    uuid_part = stem.split("_")[0]
    hexes = uuid_part.split("-")
    if len(hexes) != 5:
        return None
    try:
        return bytes(int(h[i:i + 2], 16) for h in hexes for i in range(0, len(h), 2))
    except ValueError:
        return None


def load_name(path):
    """Read just enough of the JSON to get "name" without parsing megabytes."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            # "name" sits in the first few hundred bytes of every file.
            head = fh.read(4096)
    except OSError:
        return None
    key = '"name"'
    i = head.find(key)
    if i < 0:
        return None
    j = head.find('"', head.find(":", i) + 1)
    k = head.find('"', j + 1)
    if j < 0 or k < 0:
        return None
    return head[j + 1:k]


def c_array(b):
    parts = ["0x%02x" % x for x in b]
    return ("    " + ", ".join(parts[:8]) + ",\n"
            "    " + ", ".join(parts[8:]) + ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", nargs="?")
    ap.add_argument("--grep", help="list templates whose name contains this")
    args = ap.parse_args()

    if not os.path.isdir(TPL_DIR):
        sys.exit("missing %s" % TPL_DIR)

    if args.grep:
        needle = args.grep.lower()
        hits = []
        for fn in sorted(os.listdir(TPL_DIR)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(TPL_DIR, fn)
            name = load_name(path)
            if name and needle in name.lower():
                hits.append((name, path))
        print("templates matching %r: %d" % (args.grep, len(hits)))
        for name, path in hits:
            b = uuid_bytes_from_path(path)
            print("  %-60s %s" % (name, b.hex()))
        return

    if not args.name:
        sys.exit("give a template name, or --grep <substring>")

    target = args.name
    for fn in sorted(os.listdir(TPL_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(TPL_DIR, fn)
        if load_name(path) != target:
            continue
        b = uuid_bytes_from_path(path)
        print("name   : %s" % target)
        print("file   : %s" % fn)
        print("guid   : %s" % b.hex())
        print("bytes  :")
        print(c_array(b))
        print("float-cast OK: %s" % (len(b) == 16))
        return
    sys.exit("template %r not found" % target)


if __name__ == "__main__":
    main()
