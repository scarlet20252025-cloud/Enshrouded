import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
rblob = blob[0x13AEA00:0x13AEA00+0xC04CEE]
RVA = 0x1413B0000
# The thunks are laid out contiguously at 0x1402819C0.., spaced 0x20 apart.
# Look for an rdata pointer that equals ANY thunk address (contiguous block 0x1402819C0 + 0x20*n)
base = 0x1402819C0
thunks = set()
i = 0
while True:
    a = base + 0x20*i
    if a > 0x140281A00 + 0x40: break
    thunks.add(a); i += 1
print("looking for:", [hex(t) for t in sorted(thunks)])
hits = []
for k in range(0, len(rblob)-8, 8):
    v = struct.unpack_from("<Q", rblob, k)[0]
    if v in thunks:
        hits.append((RVA+k, v))
print("hits:", len(hits))
for va, v in hits[:20]:
    print(f"  rdata rva 0x{va:X} -> 0x{v:X}")
