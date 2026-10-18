#!/usr/bin/env python3
"""Inspect a KFC TemplateResource JSON: list its component types and key values."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GUID = "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json"
PATH = os.path.join(ROOT, "tools", "kfc", "unpacked", "TemplateResource", GUID)


def main(path=PATH):
    d = json.load(open(path, encoding="utf-8"))
    print("name   =", d.get("name"))
    print("family =", d.get("family"))
    print("guid   =", d.get("$guid"))
    comps = d.get("components", [])
    print("components:", len(comps))
    for c in comps:
        t = c.get("$type")
        v = c.get("$value")
        extra = ""
        if isinstance(v, dict):
            if "faction" in v:
                extra = "  faction=%r" % (v["faction"],)
            elif "isTame" in v:
                extra = "  isTame=%r" % (v["isTame"],)
            elif "type" in v and t.endswith("Animal"):
                extra = "  type=%r" % (v["type"],)
        print("   %-52s%s" % (t, extra))


if __name__ == "__main__":
    main(*sys.argv[1:])
