import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
byidx = {t["index"]: t for t in d["types"]}
def nm(i):
    t = byidx.get(i); return t["qualifiedName"] if t else f"<{i}>"
def dump(z, maxf=30):
    h = [t for t in d["types"] if t["qualifiedName"] == z]
    if not h: print(f"!!! {z} missing"); return
    t = h[0]
    print("="*74)
    print(f"{z} idx={t['index']} size={t['size']} ptype={t['primitiveType']} fields={t['fieldCount']} qh=0x{t['qualifiedHash']:08X}")
    sf = t.get("structFields") or {}
    ef = t.get("enumFields") or {}
    if ef:
        for k,v in ef.items(): print(f"    {k} = {v['value']}")
    elif 0 < len(sf) <= maxf:
        for k,v in sf.items(): print(f"   +{v['dataOffset']:<5} {k:<30} {nm(v['type'])}")
for z in ("keen::VersionedData","keen::WorldPosition","keen::Guid",
          "keen::ecs::AdminTeleportAction","keen::ecs::EnemyDebugAction",
          "keen::ecs::ClientCamera","keen::Time"):
    dump(z)
