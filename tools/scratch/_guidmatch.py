import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
# M182 GUID_PLAYER bytes d6 66 db c3 a5 89 6c 4a a8 e3 d9 a1 f6 00 98 12
b = bytes([0xd6,0x66,0xdb,0xc3,0xa5,0x89,0x6c,0x4a,0xa8,0xe3,0xd9,0xa1,0xf6,0x00,0x98,0x12])
g = "%02x%02x%02x%02x-%02x%02x-%02x%02x-%02x%02x-%02x%02x%02x%02x%02x%02x" % (
    b[3],b[2],b[1],b[0], b[5],b[4], b[7],b[6], b[8],b[9], b[10],b[11],b[12],b[13],b[14],b[15])
print("target guid:", g)
hit = []
for fn in os.listdir(root):
    if not fn.endswith(".json"): continue
    p = os.path.join(root, fn)
    try:
        d = json.load(open(p, "r", encoding="utf-8", errors="ignore"))
    except Exception:
        continue
    if isinstance(d, dict) and str(d.get("$guid","")).lower() == g:
        hit.append((d.get("name"), fn, len(d.get("components") or [])))
for h in hit:
    print("MATCH:", h)
if not hit:
    print("no template has that guid (player is a runtime-spawned entity)")