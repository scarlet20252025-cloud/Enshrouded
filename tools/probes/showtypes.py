import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
d = json.load(open(REFL, encoding="utf-8"))
types = d["types"]

def show(idx, label=""):
    t = types[idx]
    print(f"=== types[{idx}] {label or t.get('qualifiedName','?')} size={t.get('size')} ===")
    for k, v in t.items():
        if k in ("fields", "enumValues", "attributes"):
            continue
        print(f"  {k}: {v}")
    f = t.get("fields") or []
    print(f"  fields ({len(f)}):")
    for e in f:
        if isinstance(e, dict):
            print("   ", {k: e.get(k) for k in ("name", "type", "typeIndex", "primitiveType", "offset", "size")})
        else:
            print("   ", e)
    ev = t.get("enumValues")
    if ev:
        print("  enumValues:")
        for e in ev:
            print("   ", e)
    print()

for i in (3552, 989, 2887, 2898, 3298):
    show(i)
