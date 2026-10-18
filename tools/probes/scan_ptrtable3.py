import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()

def pe_sections():
    e = struct.unpack_from("<I", blob, 0x3C)[0]
    coff = e + 4
    n = struct.unpack_from("<H", blob, coff+2)[0]
    osz = struct.unpack_from("<H", blob, coff+16)[0]
    so = coff + 20 + osz
    out = []
    for k in range(n):
        o = so + 40*k
        nm = blob[o:o+8].rstrip(b"\0").decode("latin1")
        vs, va, rs, rp = struct.unpack_from("<IIII", blob, o+8)
        out.append((nm, va, rp, rs, vs))
    return out

SECS = pe_sections()
TEXT = next(s for s in SECS if s[0] == ".text")
TEXT_RAW, TEXT_VA, TEXT_SZ = TEXT[2], 0x140000000 + TEXT[1], TEXT[3]

text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

# Registration thunk: C7 01 <hash> | 48 89 51 08 | 48 C7 41 10 <size> | C3
SIG2 = b"\x48\x89\x51\x08\x48\xc7\x41\x10"
thunks = []
i = 0
while i < len(text) - 22:
    if text[i] == 0xC7 and text[i+1] == 0x01:
        j = i + 6
        if text[j:j+8] == SIG2 and text[j+12] == 0xC3:
            h = struct.unpack_from("<I", text, i+2)[0]
            thunks.append((TEXT_VA + i, h))
    i += 1
print(f"registration thunks: {len(thunks)}")
print("PlayerInput thunk present:", any(v == 0x140281A00 for v, _ in thunks))

# Now scan every section for 8-byte LE pointers to any thunk
tset = {v for v, _ in thunks}
for nm, va, rp, rs, vs in SECS:
    s = blob[rp:rp+rs]
    hits = []
    for k in range(0, len(s)-8, 8):
        v = struct.unpack_from("<Q", s, k)[0]
        if v in tset:
            hits.append((0x140000000+va+k, v))
    print(f"{nm:8s}: {len(hits)} thunk pointers")

# Also: scan whole file for any 8-byte value equal to a thunk
print()
for v, h in thunks[:5]:
    pat = struct.pack("<Q", v)
    print(f"thunk 0x{v:X} hash 0x{h:08X}: raw occurrences in file = {blob.count(pat)}")
