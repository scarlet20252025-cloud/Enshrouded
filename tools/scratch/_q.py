import json, sys
p = r"tools\kfc\reflection_data.json"
d = json.load(open(p, encoding="utf-8"))
types = d["types"] if isinstance(d, dict) else d
for t in types:
    n = t.get("qualifiedName") or t.get("name") or ""
    if "Spawn" in n and ("Event" in n or "Command" in n or "Entity" in n):
        print(t.get("index"), t.get("size"), n)
