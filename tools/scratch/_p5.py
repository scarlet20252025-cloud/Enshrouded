import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json", encoding="utf-8"))
byidx = {t["index"]: t for t in d["types"]}
t = byidx[2066]
print("FactionType enum:")
sf = t.get("structFields") or {}
for k, v in sf.items():
    print(f"   {k} = {v}")
