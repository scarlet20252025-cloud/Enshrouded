r"""Templates are stored as <guid>_<n>_<n>.json. Map the readable name -> file
by loading every JSON's `name` field, then dump the three we care about.
"""
import io
import json
import os

ROOT = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\unpacked\TemplateResource"
WANT = [
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed",
    "Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed_Night_Patrol",
    "Enemy_Wildbeast_wolf_earlygame",
]
OUT = r"E:\DSH\肥鱼乐园\WolfMount\tools\_name_index.json"


def main():
    idx = {}
    for fn in os.listdir(ROOT):
        if not fn.endswith(".json"):
            continue
        try:
            d = json.load(io.open(os.path.join(ROOT, fn), "r", encoding="utf-8"))
        except Exception:
            continue
        nm = d.get("name")
        if nm:
            idx[nm] = fn
    json.dump(idx, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False,
              indent=1)
    print("indexed %d template names" % len(idx))
    for w in WANT:
        print("%s -> %s" % (w, idx.get(w)))


if __name__ == "__main__":
    main()
