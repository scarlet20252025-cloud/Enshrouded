#!/usr/bin/env python3
"""Runtime experiment: does the game ever write Animal/Wildlife components?

Static analysis cannot answer this: a component hash baked into a resource
blob (e.g. a world save or a spawned template) is read from data, never
inlined into .text, so a zero -.text-reference count proves nothing.

This script uses the mod's own Enqueue hook log: every component the engine
commits through Enqueue has its hash captured. If Animal/Wildlife ever
appear there, the engine can write them at runtime.
"""
import re
import sys
from collections import Counter

LOG = (r"E:\SteamLibrary\steamapps\common\Enshrouded"
       r"\wolfmount_layer.dll.log")

WANT = {
    0x8FB61D93: "Animal",
    0x5409DE31: "Wildlife",
    0x78D0C978: "UnitTransformer",
    0x92E0AA29: "NetworkWildlife",
    0x1399E0BA: "IsTame",
    0xA1F30F21: "Faction",
}


def main(path=LOG):
    seen = Counter()
    comp_re = re.compile(
        r"COMP #\d+\s+(\S+)\s+\(0x([0-9A-Fa-f]{8})\)\s+size=(\d+)\s+eid=(\d+)")
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = comp_re.search(line)
            if m:
                seen[int(m.group(2), 16)] = m.group(1)
    print("distinct component hashes observed through Enqueue: %d" % len(seen))
    for h, name in sorted(WANT.items()):
        hit = seen.get(h)
        print("   %-18s 0x%08X  %s" % (name, h, hit if hit else "-- never seen --"))
    print()
    print("all observed (top 40):")
    for h, n in seen.most_common(40):
        print("   0x%08X  %s" % (h, n))


if __name__ == "__main__":
    main(*sys.argv[1:])
