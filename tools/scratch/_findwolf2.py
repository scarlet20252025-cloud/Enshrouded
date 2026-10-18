import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
names = []
for fn in os.listdir(root):
    if not fn.endswith(".json"): continue
    p = os.path.join(root, fn)
    try:
        d = json.load(open(p, "r", encoding="utf-8", errors="ignore"))
    except Exception:
        continue
    nm = ""
    if isinstance(d, dict):
        nm = d.get("name") or d.get("Name") or ""
        if not nm:
            data = d.get("data")
            if isinstance(data, dict):
                nm = data.get("name") or data.get("Name") or ""
    if nm:
        names.append((nm, fn))
print("named templates:", len(names))
for nm, fn in sorted(names):
    if "wolf" in nm.lower():
        print(nm, "|", fn)