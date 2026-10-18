import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
guidfile = "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json"
d = json.load(open(os.path.join(root, guidfile), encoding="utf-8", errors="ignore"))
print("name:", d.get("name"))
print("family:", d.get("family"))
print("$guid:", d.get("$guid"))
comps = d.get("components")
print("components n=", len(comps) if comps is not None else None)
names = []
for c in comps or []:
    if isinstance(c, dict):
        names.append(c.get("$type") or c.get("type"))
for n in names:
    print("  ", n)