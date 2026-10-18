#!/usr/bin/env python3
"""Diff the component sets of two KFC TemplateResource JSONs."""
import json
import sys

BASE = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource"

WOLF = "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json"
TAME = "08365b0a-2205-45d7-8f02-fecabd5d32db_39768775_0.json"


def load(fn):
    d = json.load(open(BASE + "\\" + fn, encoding="utf-8"))
    comps = {}
    for c in d.get("components", []):
        comps[c.get("$type")] = c.get("$value")
    return d.get("name"), comps


def main(a=WOLF, b=TAME):
    n1, c1 = load(a)
    n2, c2 = load(b)
    print("A =", n1, " (%d components)" % len(c1))
    print("B =", n2, " (%d components)" % len(c2))
    print()
    print("--- only in A ---")
    for k in sorted(set(c1) - set(c2)):
        print("   ", k)
    print("--- only in B ---")
    for k in sorted(set(c2) - set(c1)):
        print("   ", k)
    print("--- both ---", len(set(c1) & set(c2)))


if __name__ == "__main__":
    main(*sys.argv[1:])
