import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
for fn in os.listdir(root):
    if not fn.endswith(".json"): continue
    p = os.path.join(root, fn)
    try:
        d = json.load(open(p, "r", encoding="utf-8", errors="ignore"))
    except Exception:
        continue
    if not isinstance(d, dict): continue
    nm = d.get("name") or ""
    if nm in ("Player", "PlayerCharacter", "Base_Player", "Ent_Player"):
        print(nm, "->", d.get("$guid"), "| file", fn)
    if "player" in nm.lower() and len(nm) < 40:
        print("  cand:", nm, d.get("$guid"))