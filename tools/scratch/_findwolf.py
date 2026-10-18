import os, sys, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
hits = []
for fn in os.listdir(root):
    p = os.path.join(root, fn)
    if not fn.endswith(".json"): continue
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        head = f.read(4000)
    if "wolf" in head.lower():
        hits.append((fn, head[:200]))
    if len(hits) >= 15: break
for h in hits:
    print(h[0])
print("total found:", len(hits))