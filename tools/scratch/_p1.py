import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json", encoding="utf-8"))
hits = [t for t in d["types"] if "pide" in t["qualifiedName"].lower() or "Pide" in t["qualifiedName"]]
for t in hits[:40]:
    print(f"idx={t['index']:<6} size={t['size']:<5} {t['qualifiedName']}")
print("total:", len(hits))
