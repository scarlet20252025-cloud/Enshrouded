import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
guidfile = "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json"
d = json.load(open(os.path.join(root, guidfile), encoding="utf-8", errors="ignore"))
comps = d["components"]
for c in comps:
    if c.get("$type") in ("keen::ecs::Faction","keen::ecs::CurrentTransform","keen::ecs::Health"):
        print(json.dumps(c, ensure_ascii=False)[:400])
        "----"