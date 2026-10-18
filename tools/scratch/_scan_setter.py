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
T=[s for s in secs if s[0]==".text"][0]
tstart,tend=T[3],T[3]+T[4]

def scan(hashval, label):
    needle = struct.pack("<I", hashval)
    i=tstart; out=[]
    while True:
        i=data.find(needle,i,tend)
        if i<0: break
        # check preceding bytes look like: C7 <modrm> 0C  (mov dword [reg+0xC], imm32)
        if i>=3 and data[i-3]==0xC7 and data[i-1]==0x0C:
            rva,_=loc(i); out.append((rva,data[i-3:i+8].hex(" ")))
        i+=1
    print(f"{label} 0x{hashval:08X}: {len(out)} writer(s)")
    for rva,b in out: print(f"    rva 0x{rva-3:X}  {b}")

scan(0xA1F30F21,"Faction")
scan(0x1399E0BA,"IsTame")
scan(0x027AC564,"CurrentTransform")
