import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p, "rb").read()
# sections from llvm-objdump -h
secs = [(0x400,0x13AE480,0x140001000,".text"),
        (0x13AEA00,0xC04CEE,0x1413B0000,".rdata"),
        (0x1FAEA00,0x1B200,0x141FB5000,".data")]
def where(off):
    for raw,sz,va,nm in secs:
        if raw <= off < raw+sz: return f"{nm} rva 0x{va+off-raw-0x140000000:X}"
    return "?"
for name,h in [("PlayerInput",0xFB4F945A),("AdminSpawnCommand",0x06DBFCA2),
               ("AdminSpawnCommand_internal",0x7E094D8A),("AdminDebugEnemyAction",0x14CC3955),
               ("ScenePlayerCamera",0xAB8BF04F)]:
    pat = struct.pack("<I", h)
    off = 0; hits=[]
    while True:
        i = data.find(pat, off)
        if i < 0: break
        hits.append(i); off = i+1
    print(f"{name} 0x{h:08X}: {len(hits)} hits")
    for i in hits[:12]:
        print(f"    file 0x{i:X}  {where(i)}")
