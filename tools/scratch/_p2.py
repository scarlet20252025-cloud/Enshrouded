import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json", encoding="utf-8"))
for nm in ("keen::ecs::HitEvent", "keen::ecs::BaseHitEvent"):
    for t in d["types"]:
        if t["qualifiedName"] == nm:
            print("="*70)
            print(nm, "idx=", t["index"], "size=", t["size"], "fields=", t.get("fieldCount"))
            for f in t.get("fields", []):
                print(f"   +{f.get('offset'):<4} {f.get('name'):<28} type={f.get('typeName')}")
