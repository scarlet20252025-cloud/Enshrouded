import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
# .reloc section VA 0x14295E000 raw 0x311DC00 size 0x11BE0
# .bind  section VA 0x1429E0000 raw 0x312F800 size 0x2C1C0
# Look at reloc entries pointing into .text region containing thunk 0x140281A00
rel = blob[0x311DC00:0x311DC00+0x11BE0]
# parse base relocation blocks
off = 0
blocks = 0
target_va = 0x140281A00
hits = []
while off + 8 <= len(rel):
    page_rva, blk_sz = struct.unpack_from("<II", rel, off)
    if blk_sz == 0: break
    blocks += 1
    n = (blk_sz - 8)//2
    for k in range(n):
        e = struct.unpack_from("<H", rel, off+8+2*k)[0]
        typ = e >> 12
        o = e & 0xFFF
        if typ == 0: continue
        rva = page_rva + o
        va = 0x140000000 + rva
        if 0x140281900 <= va <= 0x140281B00:
            hits.append((rva, va, typ))
    off += blk_sz
print("reloc blocks:", blocks, "hits near thunk:", hits)
