r"""Print full SpawnEntityBaseEvent field table (name -> dataOffset) in order,
plus TameWildlifeEvent/SequenceEvent/Time so we can build a spawn payload."""
import json
import os

RD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "tools", "kfc", "reflection_data.json")

WANT = [1859, 1863, 1762, 1761, 1900, 1079, 1045, 1046]


def main():
    d = json.load(open(RD, encoding="utf-8"))
    by_idx = {t["index"]: t for t in d["types"]}
    for i in WANT:
        t = by_idx[i]
        print("=" * 72)
        print("%s  idx=%d size=%s" % (t["qualifiedName"], i, t.get("size")))
        sf = t.get("structFields") or {}
        rows = []
        for fname, meta in sf.items():
            rows.append((meta.get("dataOffset"), fname, meta.get("type")))
        for off, fname, ty in sorted(rows):
            tname = by_idx.get(ty, {}).get("qualifiedName", "?")
            print("   +%-5s %-38s %s" % (off, fname, tname))


if __name__ == "__main__":
    main()
