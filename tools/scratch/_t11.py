import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
# find .reloc raw offset via llvm-objdump -h (long) or via section table parse
# Use PE header parse properly
import struct
dos = blob[:2]
assert dos == b"MZ", dos
e_lfanew = struct.unpack_from("<I", blob, 0x3C)[0]
assert blob[e_lfanew:e_lfanew+4] == b"PE\0\0"
coff = e_lfanew + 4
nsec = struct.unpack_from("<H", blob, coff+2)[0]
opt_sz = struct.unpack_from("<H", blob, coff+16)[0]
sec_off = coff + 20 + opt_sz
secs = []
for k in range(nsec):
    o = sec_off + 40*k
    name = blob[o:o+8].rstrip(b"\0").decode("latin1")
    vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", blob, o+8)
    secs.append((name, vaddr, rawptr, rawsize, vsize))
for s in secs: print(s)
