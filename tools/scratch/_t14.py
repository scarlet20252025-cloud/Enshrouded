import sys, io, struct, json, re
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

def name_of(va):
    h = None
    # search backwards up to 40 bytes for a mov reg,imm32 (BA/B8/B9/BB/BD/BE/BF/41 B8/41 B9)
    off = va - TEXT_VA
    for back in range(0, 60):
        i = off - back
        if i < 1: break
        b = text[i]
        if b in (0xB8,0xB9,0xBA,0xBB,0xBD,0xBE,0xBF):
            h = struct.unpack_from("<I", text, i+1)[0]
            return h, f"mov r{ {0xB8:8,0xB9:1,0xBA:2,0xBB:3,0xBD:5,0xBE:6,0xBF:7}[b] },imm32 @0x{TEXT_VA+i:X}"
        if b == 0x41 and i>0 and text[i+1] in (0xB8,0xB9):
            h = struct.unpack_from("<I", text, i+2)[0]
            return h, f"mov r{8 if text[i+1]==0xB8 else 9},imm32 @0x{TEXT_VA+i:X}"
    return None, None

target = 0x140955400
i = 0
rows = []
while i < len(text)-5:
    if text[i] == 0xE8:
        rel = struct.unpack_from("<i", text, i+1)[0]
        if TEXT_VA+i+5+rel == target:
            va = TEXT_VA+i
            h, how = name_of(va)
            nm = by_qh.get(h, {}).get("qualifiedName", "?") if h else "?"
            rows.append((va, h, nm, how))
    i += 1
print(f"SendEvent callers: {len(rows)}")
for va, h, nm, how in sorted(rows):
    print(f"0x{va:X}  {('0x%08X'%h) if h else '--------':>10}  {nm}")
