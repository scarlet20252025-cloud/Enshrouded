import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
byidx = {t["index"]: t for t in d["types"]}
def dump(nm, show_fields=True, maxf=40):
    hits = [t for t in d["types"] if t["qualifiedName"] == nm]
    if not hits:
        print(f"!!! not found: {nm}"); return
    t = hits[0]
    print("="*72)
    print(f"{nm}  idx={t['index']} size={t['size']} ptype={t['primitiveType']} fields={t['fieldCount']} inner={t['innerType']}")
    print(f"   qualifiedHash=0x{t['qualifiedHash']:08X}")
    sf = t.get("structFields") or {}
    if show_fields and 0 < len(sf) <= maxf:
        for k,v in sf.items():
            tn = byidx.get(v["type"],{}).get("qualifiedName", f"type{v['type']}")
            print(f"   +{v['dataOffset']:<5} {k:<28} {tn}")
for nm in ("keen::ecs::PlayerInput","keen::ecs::ClientPlayerInput","keen::ecs::AdminClientPlayerInputData",
           "keen::ecs::AdminSpawnCommand","keen::ecs::AdminDebugEnemyAction","keen::ecs::AdminTeleport",
           "keen::ecs::AdministrationClientData","keen::ecs::AdminClientData"):
    dump(nm)
