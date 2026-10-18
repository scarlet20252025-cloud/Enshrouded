import json
d=json.load(open(r"tools\kfc\reflection_data.json","r",encoding="utf-8"))
types = d["types"] if isinstance(d,dict) and "types" in d else d
def qname(t):
    return t.get("qualifiedName") or t.get("name")
def show(i,depth=0,seen=None):
    seen = seen or set()
    if i in seen or depth>3: return
    seen.add(i)
    t=types[i]
    print("%s[%d] %s size=%s ptype=%s inner=%s" % ("  "*depth,i,qname(t),t.get("size"),t.get("primitiveType"),t.get("innerType")))
    sf=t.get("structFields") or []
    ef=t.get("enumFields") or []
    if sf:
        for f in sf:
            if isinstance(f,str):
                print("%s  field %s" % ("  "*depth,f))
            else:
                print("%s  field %-26s off=%s type=%s" % ("  "*depth,f.get("name"),f.get("dataOffset"),f.get("type")))
    if ef:
        for f in ef:
            if isinstance(f,str):
                print("%s  enum %s" % ("  "*depth,f))
            else:
                print("%s  enum %-26s val=%s" % ("  "*depth,f.get("name"),f.get("value")))
    it=t.get("innerType")
    if isinstance(it,int) and it!=i:
        show(it,depth+1,seen)

for want in ["keen::WeaponCategoryId","keen::impact::DamageTypeMask","keen::impact::AttackCategoryMask"]:
    for i,t in enumerate(types):
        if qname(t)==want:
            print("############",want); show(i); break
