import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json", encoding="utf-8"))
ts = {t["qualifiedName"]: t for t in d["types"]}
t = ts["keen::ecs::HitEvent"]
print("KEYS:", list(t.keys()))
print(json.dumps(t, ensure_ascii=False, indent=1)[:3000])
