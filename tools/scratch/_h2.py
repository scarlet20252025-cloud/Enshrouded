import struct
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(EXE, "rb").read()
targets = {
 "SpawnEntityEvent":0x51E20BF3,
 "SpawnEntityBaseEvent":0x1D839DBC,
 "SpawnEntityCommomEvent":0xA8613CF3,
 "AdminSpawnCommand":0x06DBFCA2,
}
# section table
import re
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
nsec = struct.unpack_from("<H", data, e_lfanew+6)[0]
opt = struct.unpack_from("<H", data, e_lfanew+20)[0]
secs=[]
so = e_lfanew+24+opt
for i in range(nsec):
    o=so+i*40
    name=data[o:o+8].rstrip(b"\0").decode(errors="replace")
    vsize,va,rawsize,rawptr = struct.unpack_from("<IIII", data, o+8)
    secs.append((name,va,vsize,rawptr,rawsize))
for tn,h in targets.items():
    needle = struct.pack("<I", h)
    print(f"=== {tn} 0x{h:08X} ===")
    i=0; hits=[]
    while True:
        i = data.find(needle, i)
        if i<0: break
        for name,va,vsize,rawptr,rawsize in secs:
            if rawptr <= i < rawptr+rawsize:
                print(f"  file 0x{i:X} rva 0x{va+(i-rawptr):X} [{name}]")
                break
        i+=1
