import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
IMG = 0x140000000
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
def cstr(va, maxn=200):
    o = off_of(va)
    if o is None: return None
    e = data.find(b"\x00", o, o+maxn)
    if e < 0: return None
    return data[o:e].decode("utf-8","replace")

def read_rec(recva):
    b = rd(recva, 0x90)
    if not b or len(b) < 0x90: return None
    (name_ptr, name_len, imp_ptr, imp_len, qn_ptr, qn_len, ns_ptr, ns_len
     ) = struct.unpack_from("<QIIQIIQI", b, 0)
    (size, align) = struct.unpack_from("<II", b, 0x40)
    (fcount,) = struct.unpack_from("<I", b, 0x48)
    (ptype,) = struct.unpack_from("<B", b, 0x4C)
    (qh, ih) = struct.unpack_from("<II", b, 0x50)
    (sf_ptr,) = struct.unpack_from("<Q", b, 0x58)
    (ef_ptr,) = struct.unpack_from("<Q", b, 0x60)
    (dv_ptr, dv_len) = struct.unpack_from("<QI", b, 0x70)
    return dict(rec=recva, name=cstr(name_ptr,name_len) if name_ptr else None,
                qname=cstr(qn_ptr,qn_len) if qn_ptr else None,
                size=size, align=align, fcount=fcount, ptype=ptype,
                qh=qh, ih=ih, sf=sf_ptr, ef=ef_ptr, dv=dv_ptr, dvlen=dv_len)

# ScenePlayerCamera record
r = read_rec(0x141964350 + 0x0)
print("record around 0x141964350:")
for delta in (0, 0x10, 0x20, 0x30, 0x40, 0x50, 0x60, 0x70, 0x80):
    rr = read_rec(0x141964350 + delta)
    if rr and rr["qname"] and "keen::" in rr["qname"]:
        print(f"  rec=0x{rr['rec']:X} qname={rr['qname']} size={rr['size']} fcount={rr['fcount']} qh=0x{rr['qh']:08X} sf=0x{rr['sf']:X}")
