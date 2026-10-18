import os, json
root = os.path.join("tools","kfc","unpacked","TemplateResource")
want = ["Enemy_Wildbeast_wolf_earlygame","Enemy_Wildbeast_Wolf_Heavy","Enemy_Wildbeast_Wolf_hook_AG2","Enemy_Wildbeast_Wolf_AutomatedTesting","Enemy_Wildlife_Wolf_Heal_LickWOunds"]
guidfile = "478381c5-585f-4264-b373-dbb1ea596eca_39768775_0.json"
d = json.load(open(os.path.join(root, guidfile), encoding="utf-8", errors="ignore"))
print(type(d))
if isinstance(d, dict):
    for k in list(d.keys())[:25]:
        print("KEY:", k)
    guid = d.get("guid")
    print("GUID:", guid)
    data = d.get("data")
    print("data type:", type(data))
    if isinstance(data, dict):
        for k in list(data.keys())[:30]:
            print("  DATA KEY:", k)
        comps = data.get("components")
        print("components type:", type(comps), "n=", len(comps) if comps is not None else None)
        if isinstance(comps, list) and comps:
            print("first comp:", json.dumps(comps[0])[:500])