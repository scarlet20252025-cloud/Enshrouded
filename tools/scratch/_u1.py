import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DLL = r"C:\Windows\System32\ucrtbase.dll"
blob = open(DLL, "rb").read()
e = struct.unpack_from("<I", blob, 0x3C)[0]
coff = e + 4
n = struct.unpack_from("<H", blob, coff+2)[0]
osz = struct.unpack_from("<H", blob, coff+16)[0]
so = coff + 20 + osz
for k in range(n):
    o = so + 40*k
    nm = blob[o:o+8].rstrip(b"\0").decode("latin1")
    vs, va, rs, rp = struct.unpack_from("<IIII", blob, o+8)
    print(f"{nm:10s} VA 0x{va:08x} raw 0x{rp:08x} size 0x{rs:08x}")
