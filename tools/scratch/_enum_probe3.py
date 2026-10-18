import json
d=json.load(open(r"tools\kfc\reflection_data.json","r",encoding="utf-8"))
types = d["types"] if isinstance(d,dict) and "types" in d else d
for want in ["keen::ecs::AdminSpawnCommand","keen::ecs::PlayerFocus","keen::ecs::PlayerInput","keen::ecs::ClientPlayerInput"]:
    for i,t in enumerate(types):
        if t.get("qualifiedName")==want:
            print("%-36s idx=%d innerType=%s ptype=%s" % (want,i,t.get("innerType"),t.get("primitiveType")))
            # is it a Component?
            it=t.get("innerType")
            if isinstance(it,int) and it < len(types):
                print("     inner -> %s" % types[it].get("qualifiedName"))
            break
