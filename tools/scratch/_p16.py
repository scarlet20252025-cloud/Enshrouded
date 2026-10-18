import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
secs = [(0x400,0x13AE480,0x140001000),
        (0x13AEA00,0xC04CEE,0x1413B0000),
        (0x1FAEA00,0x1B200,0x141FB5000)]
def off_of(va):
    for raw,sz,sva in secs:
        if sva <= va < sva+sz: return raw + (va - sva)
    return None
def rd(va,n):
    o = off_of(va)
    return None if o is None else data[o:o+n]
def cstr(va, maxn=300):
    o = off_of(va)
    if o is None: return None
    e = data.find(b"\x00", o, o+maxn)
    return None if e<0 else data[o:e].decode("utf-8","replace")

rec = 0x141A3F840  # HitEvent
b = rd(rec, 0x90)
print("raw record bytes (HitEvent @0x141A3F840):")
for i in range(0, 0x90, 16):
    print(f"  +0x{i:02X}  {b[i:i+16].hex(' ')}")
print()
# scan every 8-byte aligned qword for a pointer that resolves to a printable string
for i in range(0, 0x90, 8):
    q, = struct.unpack_from("<Q", b, i)
    s = cstr(q, 120) if q else None
    u, = struct.unpack_from("<I", b, i)
    print(f"  +0x{i:02X} q=0x{q:016X} u32={u:<12} str={s!r}")
