r"""Print raw JSON records for the types we need, so we can see the actual
ObjectReference field names (the dumper only prints innerType)."""
import json
import os

RD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "tools", "kfc", "reflection_data.json")

WANT_IDX = [1045, 1046, 1859, 1863, 1864, 1900, 1762, 1761, 1079]


def main():
    d = json.load(open(RD, encoding="utf-8"))
    types = d["types"]
    by_idx = {t["index"]: t for t in types}
    for i in WANT_IDX:
        t = by_idx.get(i)
        if not t:
            print("no idx %d" % i)
            continue
        print("=" * 70)
        print("idx=%d keys=%s" % (i, sorted(t.keys())))
        print(json.dumps(t, ensure_ascii=False, indent=1)[:1400])


if __name__ == "__main__":
    main()
