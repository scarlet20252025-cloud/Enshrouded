import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
by_qh = {t["qualifiedHash"]: t for t in json.load(open(REFL, encoding="utf-8"))["types"]}
blob = open(EXE, "rb").read()
e = struct.unpack_from("<I", blob, 0x3C)[0]
coff = e + 4
n = struct.unpack_from("<H", blob, coff+2)[0]
osz = struct.unpack_from("<H", blob, coff+16)[0]
so = coff + 20 + osz
secs = []
for k in range(n):
    o = so + 40*k
    nm = blob[o:o+8].rstrip(b"\0").decode("latin1")
    vs, va, rs, rp = struct.unpack_from("<IIII", blob, o+8)
    secs.append((nm, va, rp, rs, vs))
t = next(s for s in secs if s[0]==".text")
TEXT_RAW, TEXT_VA, TEXT_SZ = t[2], 0x140000000+t[1], t[3]
text = blob[TEXT_RAW:TEXT_RAW+TEXT_SZ]

# For each SendEvent call site, walk BACKWARD from the call, decoding a small
# instruction stream, looking for "movl $imm32, %edx" (BA imm32) or
# "movl $imm32, %r8d" (41 B8) that are within 30 bytes before the call.
def scan_back(va, dist=48):
    off = va - TEXT_VA
    res = {}
    for back in range(5, dist):
        i = off - back
        if i < 1: break
        if text[i] == 0xBA:
            res.setdefault("edx", struct.unpack_from("<I", text, i+1)[0])
        elif text[i] == 0x41 and text[i+1] == 0xB8:
            res.setdefault("r8d", struct.unpack_from("<I", text, i+2)[0])
    return res

target = 0x140955400
i = 0
rows = []
while i < len(text)-5:
    if text[i] == 0xE8:
        rel = struct.unpack_from("<i", text, i+1)[0]
        if TEXT_VA+i+5+rel == target:
            va = TEXT_VA+i
            r = scan_back(va)
            h = r.get("edx")
            rows.append((va, h, r.get("r8d")))
    i += 1
from collections import Counter
c = Counter((h, by_qh.get(h,{}).get("qualifiedName","?")) for _,h,_ in rows if h)
print("distinct type hashes sent via SendEvent:", len(c))
for (h, nm), cnt in c.most_common():
    print(f"  0x{h:08X}  x{cnt:<3}  {nm}")
print()
unknown = [(va,h) for va,h,_ in rows if h and h not in by_qh]
print("sites with unknown hash:", len(unknown))
for va,h in unknown[:20]:
    print(f"  0x{va:X} 0x{h:08X}")
