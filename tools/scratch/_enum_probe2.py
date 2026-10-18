import json
d=json.load(open(r"tools\kfc\reflection_data.json","r",encoding="utf-8"))
types = d["types"] if isinstance(d,dict) and "types" in d else d
for i in (3126,3294):
    t=types[i]
    print("###",i,t.get("qualifiedName"))
    print(json.dumps(t, ensure_ascii=False)[:1200])
