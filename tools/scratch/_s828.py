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
def rva_of(f):
    for name,va,vs,rp,rs in secs:
        if rp<=f<rp+rs: return va+(f-rp), name
    return None,None
# .text bounds
T=[s for s in secs if s[0]==".text"][0]
tstart,tend = T[3], T[3]+T[4]
needle = struct.pack("<I", 0x828)
i=tstart
hits=[]
while True:
    i = data.find(needle, i, tend)
    if i<0: break
    hits.append(i); i+=1
print(f"disp32 0x828 occurrences in .text: {len(hits)}")
for f in hits[:60]:
    rva,_ = rva_of(f)
    ctx = data[f-12:f+12]
    print(f"  rva 0x{rva:X}  {ctx.hex(' ')}")
