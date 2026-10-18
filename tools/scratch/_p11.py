import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
byidx = {t["index"]: t for t in d["types"]}
def nm(i):
    t = byidx.get(i)
    return t["qualifiedName"] if t else f"<idx{i}>"
def dump(nmz, maxf=60):
    hits = [t for t in d["types"] if t["qualifiedName"] == nmz]
    if not hits:
        print(f"!!! not found: {nmz}"); return None
    t = hits[0]
    print("="*74)
    print(f"{nmz}  idx={t['index']} size={t['size']} ptype={t['primitiveType']} fields={t['fieldCount']}")
    sf = t.get("structFields") or {}
    if 0 < len(sf) <= maxf:
        for k,v in sf.items():
            print(f"   +{v['dataOffset']:<5} {k:<30} {nm(v['type'])}")
    else:
        print(f"   ({len(sf)} fields; enumFields={len(t.get('enumFields') or {})})")
    return t
for n in ("keen::ecs::AdminClientPlayerInputData","keen::ecs::AdminSpawnCommand",
          "keen::ecs::AdminDebugEnemyAction","keen::ecs::AdminTeleport",
          "keen::ecs::AdminKillFactionCommand","keen::ecs::ClientPlayerInputData"):
    dump(n)
