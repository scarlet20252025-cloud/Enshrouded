import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json", encoding="utf-8"))
byidx = {t["index"]: t for t in d["types"]}
for i in (3292, 3293, 3296, 2066, 3128, 1312, 69, 45, 14, 728):
    t = byidx.get(i)
    if not t: 
        print(i, "MISSING"); continue
    print("="*70)
    print(f"idx={i} {t['qualifiedName']} size={t['size']} ptype={t['primitiveType']} fields={t['fieldCount']}")
    sf = t.get("structFields") or {}
    if len(sf) > 0 and len(sf) < 60:
        for k, v in sf.items():
            print(f"    {k} = {v}")
    elif len(sf) >= 60:
        print(f"    ({len(sf)} entries, first 40)")
        for k, v in list(sf.items())[:40]:
            print(f"    {k}")
