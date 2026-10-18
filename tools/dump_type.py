r"""Dump a reflection type and its inheritance chain.

Usage:
    python tools/dump_type.py --idx 1762
    python tools/dump_type.py --name keen::actor::TameWildlifeEvent
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import json
import sys

RD = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")


def load():
    d = json.load(open(RD, encoding="utf-8"))
    by_idx = {t["index"]: t for t in d["types"]}
    return d, by_idx


def prim(by_idx, idx):
    t = by_idx.get(idx)
    if not t:
        return "?%d" % idx
    if t.get("primitiveType") == "PRIMITIVE" or (
            t.get("primitiveType") not in ("STRUCT", "ENUM")):
        return t.get("name", "?")
    return t.get("qualifiedName") or t.get("name")


def dump(by_idx, idx, depth=0, seen=None):
    if seen is None:
        seen = set()
    t = by_idx.get(idx)
    if not t:
        print("  " * depth + "?? idx %d missing" % idx)
        return
    pad = "  " * depth
    qn = t.get("qualifiedName") or t.get("name")
    print("%s%s  idx=%d size=%s align=%s ptype=%s"
          % (pad, qn, t["index"], t.get("size"), t.get("alignment"),
             t.get("primitiveType")))

    inner = t.get("innerType")
    if inner is not None and inner not in seen:
        seen = seen | {inner}
        print("%s  -- innerType --" % pad)
        dump(by_idx, inner, depth + 1, seen)

    sf = t.get("structFields") or {}
    for name, f in sf.items():
        print("%s  +%-5s %-28s %s"
              % (pad, f.get("dataOffset"), f.get("name"),
                 prim(by_idx, f.get("type"))))
    ef = t.get("enumFields") or {}
    if ef:
        for name, f in list(ef.items())[:40]:
            print("%s  %-24s = %s" % (pad, name, f.get("value")))


def main():
    d, by_idx = load()
    args = sys.argv[1:]
    if "--idx" in args:
        i = args.index("--idx")
        dump(by_idx, int(args[i + 1]))
    elif "--name" in args:
        i = args.index("--name")
        want = args[i + 1]
        hits = [t for t in d["types"] if t.get("qualifiedName") == want]
        if not hits:
            hits = [t for t in d["types"]
                    if want.lower() in (t.get("qualifiedName") or "").lower()]
        print("=== %d hit(s)" % len(hits))
        for t in hits[:6]:
            dump(by_idx, t["index"])
            print()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
