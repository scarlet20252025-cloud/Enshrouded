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

ARRAY_VA = 0x1416FD950
CNT = 12646
print(f"array VA 0x{ARRAY_VA:X} count {CNT}")
b = rd(ARRAY_VA, 8*8)
print("first 8 entries:", [hex(x) for x in struct.unpack_from("<8Q", b, 0)])

def read_rec(recva):
    b = rd(recva, 0x90)
    if not b or len(b)<0x90: return None
    name_ptr, name_len, imp_ptr, imp_len, qn_ptr, qn_len, ns_ptr, ns_len = struct.unpack_from("<QIIQIIQI", b, 0)
    size, align = struct.unpack_from("<II", b, 0x40)
    fcount, = struct.unpack_from("<I", b, 0x48)
    ptype, = struct.unpack_from("<B", b, 0x4C)
    qh, ih = struct.unpack_from("<II", b, 0x50)
    sf, = struct.unpack_from("<Q", b, 0x58)
    ef, = struct.unpack_from("<Q", b, 0x60)
    dv, dvlen = struct.unpack_from("<QI", b, 0x70)
    return dict(rec=recva, name=cstr(name_ptr,name_len) if name_ptr else None,
                qname=cstr(qn_ptr,qn_len) if qn_ptr else None,
                size=size, fcount=fcount, ptype=ptype, qh=qh, ih=ih, sf=sf, ef=ef,
                dv=dv, dvlen=dvlen)

for idx in (0, 127, 136, 208, 732, 881, 989, 1900, 2887, 2898, 3298, 3635, 2066):
    ptrs = rd(ARRAY_VA + idx*8, 8)
    if not ptrs: print(idx, "OOB"); continue
    pv, = struct.unpack("<Q", ptrs)
    r = read_rec(pv)
    if not r: print(idx, "unreadable ptr", hex(pv)); continue
    print(f"idx={idx:<6} rec=0x{r['rec']:X} size={r['size']:<5} f={r['fcount']:<4} pt={r['ptype']:<3} qh=0x{r['qh']:08X} {r['qname']}")
