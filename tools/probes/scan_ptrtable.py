import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"

by_qh = {t["qualifiedHash"]: t for t in json.load(open(REFL, encoding="utf-8"))["types"]}

blob = open(EXE, "rb").read()
# section map (from llvm-objdump -h)
#  name   VA           raw      size
SECTS = [
    (".text",  0x140001000, 0x400,       0x13AE480),
    (".rdata", 0x1413B0000, 0x13AEA00,   0xC04CEE),
    (".data",  0x141FB5000, 0x1FAEA00,   0x1B200),
    (".pdata", 0x142836000, 0x2160A00,   0xD4FC4),
    (".rsrc",  0x14290B000, 0x2E35C00,   0x2E8000),
    (".reloc", 0x14295E000, 0x311DC00,   0x11BE0),
    (".bind",  0x1429E0000, 0x312F800,   0x2C1C0),
]

def rva_to_off(va):
    for name, vaddr, raw, size in SECTS:
        if vaddr <= va < vaddr + size:
            return raw + (va - vaddr)
    return None

# Find, in .rdata, every 8-byte little-endian value that equals one of the
# registration thunk addresses -> that is a function-pointer table entry.

thunks = []
# re-derive thunks: pattern C7 01 <hash> / 48 89 51 08 / 48 C7 41 10 <size> / C3
TEXT_RAW, TEXT_VA, TEXT_SZ = SECTS[0][2], SECTS[0][1], SECTS[0][3]
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]
SIG2 = b"\x48\x89\x51\x08\x48\xc7\x41\x10"
print("TEXT_SZ =", hex(TEXT_SZ), "len(text) =", hex(len(text)))
i = 0
while i < TEXT_SZ - 22:
    if text[i] == 0xC7 and text[i+1] == 0x01:
        j = i + 6
        if text[j:j+8] == SIG2 and text[j+12] == 0xC3:
            thunks.append(TEXT_VA + i)
    i += 1

print(f"thunks: {len(thunks)}")
if 0x140281A00 not in thunks:
    print("WARN: known thunk 0x140281A00 not detected")
# scan .rdata for pointers to thunks
rdata = SECTS[1]
rblob = blob[rdata[2]:rdata[2]+rdata[3]]
tset = {t: k for k, t in enumerate(thunks)}
hits = []
for k in range(0, len(rblob) - 8, 8):
    v = struct.unpack_from("<Q", rblob, k)[0]
    if v in tset:
        hits.append((rdata[1] + k, v))

print(f"rdata pointer-table entries referencing thunks: {len(hits)}")
for va, tva in hits[:60]:
    print(f"  rva 0x{va:X} -> thunk 0x{tva:X}")
print(f"  ... ({len(hits)} total)")
