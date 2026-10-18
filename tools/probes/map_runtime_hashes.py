# -*- coding: utf-8 -*-
"""Map any component hashes seen in the runtime log to reflection names.

Generic: pass hashes on the command line (hex or dec). If none are given, parse
them straight out of the wolfmount log's COMP lines, so it works on whatever
the last session produced.
"""
import io
import json
import re
import sys

REF = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
LOG = r"E:\SteamLibrary\steamapps\common\Enshrouded\wolfmount_layer.dll.log"


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    d = json.load(io.open(REF, "r", encoding="utf-8"))
    types = d["types"] if isinstance(d, dict) and "types" in d else d

    # name -> index, so we can report the reflection index too (it is the
    # runtime component-type id per b18/b19).
    name_to_idx = {}
    for t in types:
        tq = t.get("qualifiedName") or t.get("name")
        if tq:
            name_to_idx[tq] = t.get("idx") or t.get("index")

    if len(sys.argv) > 1:
        want = [int(a, 0) for a in sys.argv[1:]]
    else:
        want = set()
        counts = {}
        sizes = {}
        try:
            txt = io.open(LOG, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            txt = ""
        for m in re.finditer(r"COMP #\d+ 0x([0-9A-F]+) size=(\d+)", txt):
            h = int(m.group(1), 16)
            want.add(h)
            counts[h] = counts.get(h, 0) + 1
            sizes[h] = int(m.group(2))
        # hash -> count map for the whole log is what we want to print
        if want:
            print("parsed %d distinct unnamed hashes from the log" % len(want))
            globals()["_COUNTS"] = counts
            globals()["_SIZES"] = sizes

    for h in sorted(want):
        name = None
        size = None
        for t in types:
            tq = t.get("qualifiedName") or t.get("name")
            if tq and fnv1a(tq) == h:
                name = tq
                size = t.get("size")
                break
        extra = ""
        if name:
            extra = " idx=%s" % name_to_idx.get(name, "?")
        print("0x%08X  %-52s size=%-5s%s" % (h, name or "?", size if size is not None else "?", extra))


if __name__ == "__main__":
    main()
