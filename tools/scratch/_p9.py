import sys, io, struct, uuid
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

def gbytes(s):
    u = uuid.UUID(s)
    # .NET Guid layout: first three fields little-endian
    return (u.fields[0].to_bytes(4,'little') + u.fields[1].to_bytes(2,'little')
            + u.fields[2].to_bytes(2,'little') + u.bytes[8:])

guids = {
 "wolf_earlygame":"478381c5-585f-4264-b373-dbb1ea596eca",
 "wolf_heavy":"f6a96b72-6da4-4e04-ab62-40e8d0feeac7",
 "wolf_autoTest":"0d75b9a9-7e48-4f3a-bf2a-19bf6021f531",
 "wolf_hook_AG2":"54c99a9f-d6d1-4cd9-84bb-dd001915ca98",
 "dog_bright":"5d9c1829-69fc-4339-8bcc-5e62e63e9a31",
}
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
secs = [(0x400,0x13AE480,0x140001000,".text"),
        (0x13AEA00,0xC04CEE,0x1413B0000,".rdata"),
        (0x1FAEA00,0x1B200,0x141FB5000,".data")]
def where(off):
    for raw,sz,va,nm in secs:
        if raw <= off < raw+sz: return f"{nm} rva 0x{va+off-raw-0x140000000:X}"
    return "?"
for name,g in guids.items():
    pat = gbytes(g)
    off=0; hits=[]
    while True:
        i = data.find(pat, off)
        if i<0: break
        hits.append(i); off=i+1
    print(f"{name} {g}")
    print(f"   bytes {pat.hex()}  ->  {len(hits)} hits")
    for i in hits[:10]:
        print(f"      file 0x{i:X}  {where(i)}")
