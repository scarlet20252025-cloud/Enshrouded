import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
secs = [(0x400,0x13AE480,0x140001000),(0x13AEA00,0xC04CEE,0x1413B0000),(0x1FAEA00,0x1B200,0x141FB5000)]
def off_of(va):
    for raw,sz,sva in secs:
        if sva <= va < sva+sz: return raw + (va - sva)
    return None
def rd(va,n):
    o = off_of(va); return None if o is None else data[o:o+n]
def cstr(va, maxn=200):
    o = off_of(va)
    if o is None: return None
    e = data.find(b"\x00", o, o+maxn)
    return None if e<0 else data[o:e].decode("utf-8","replace")

SF = 0x141A3B9E0   # HitEvent structFields, 22 fields
b = rd(SF, 22*24)
print("HitEvent structFields @0x%X (first 22*24 bytes):" % SF)
for i in range(0, 22*24, 16):
    print(f"  +0x{i:03X}  {b[i:i+16].hex(' ')}")

print("\n-- try parsing each 24-byte entry as {q ptr, u32 off, ...} --")
for k in range(22):
    base = k*24
    q, = struct.unpack_from("<Q", b, base)
    o1, o2, o3, o4 = struct.unpack_from("<IIII", b, base+8)
    s = cstr(q, 80) if q else None
    print(f"  [{k:2}] +0x{base:03X} q=0x{q:012X} u=({o1},{o2},{o3},{o4}) str={s!r}")
