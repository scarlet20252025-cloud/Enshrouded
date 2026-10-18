import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
secs = [(0x400,0x13AE480,0x140001000,".text"),
        (0x13AEA00,0xC04CEE,0x1413B0000,".rdata"),
        (0x1FAEA00,0x1B200,0x141FB5000,".data"),
        (0x2160A00,0xD4FC4,0x142836000,".pdata")]
def where(off):
    for raw,sz,va,nm in secs:
        if raw <= off < raw+sz: return f"{nm} rva 0x{va+off-raw-0x140000000:X}"
    return "?"
def findabs(va, label):
    pat = struct.pack("<Q", va)
    off=0; hits=[]
    while True:
        i = data.find(pat, off)
        if i<0: break
        hits.append(i); off=i+1
    print(f"\n{label}  VA 0x{va:X}  ({len(hits)} absolute pointer hits)")
    for i in hits[:20]:
        print(f"    file 0x{i:X}  {where(i)}")
    return hits

for va,lb in [(0x14047D040,"SetIsTame"),
              (0x140481070,"setter2-base-guess"),
              (0x14047D090,"fn after SetIsTame"),
              (0x140481148,"IsTame raw store2")]:
    findabs(va, lb)
