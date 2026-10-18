import struct
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(EXE,"rb").read()
e = struct.unpack_from("<I",data,0x3C)[0]
nsec = struct.unpack_from("<H",data,e+6)[0]
opt = struct.unpack_from("<H",data,e+20)[0]
so = e+24+opt
secs=[]
for i in range(nsec):
    o=so+i*40
    name=data[o:o+8].rstrip(b"\0").decode(errors="replace")
    vs,va,rs,rp = struct.unpack_from("<IIII",data,o+8)
    secs.append((name,va,vs,rp,rs))
def loc(f):
    for name,va,vs,rp,rs in secs:
        if rp<=f<rp+rs: return va+(f-rp), name
    return None,None
for hv,label in [(0xA1F30F21,"Faction"),(0x1399E0BA,"IsTame")]:
    needle=struct.pack("<I",hv)
    i=0; print(f"=== {label} 0x{hv:08X} ===")
    n=0
    while True:
        i=data.find(needle,i)
        if i<0: break
        rva,sec=loc(i)
        print(f"  file 0x{i:X} rva 0x{rva:X} [{sec}]  ctx {data[max(0,i-8):i+8].hex(' ')}")
        i+=1; n+=1
        if n>12: print("  ..."); break
