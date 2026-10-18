import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()

SECTS = [
    (".text",  0x140001000, 0x400,       0x13AE480),
    (".rdata", 0x1413B0000, 0x13AEA00,   0xC04CEE),
    (".data",  0x141FB5000, 0x1FAEA00,   0x1B200),
    (".pdata", 0x142836000, 0x2160A00,   0xD4FC4),
    (".rsrc",  0x14290B000, 0x2E35C00,   0x2E8000),
    (".reloc", 0x14295E000, 0x311DC00,   0x11BE0),
    (".bind",  0x1429E0000, 0x312F800,   0x2C1C0),
]

TEXT_RAW, TEXT_VA, TEXT_SZ = SECTS[0][2], SECTS[0][1], SECTS[0][3]
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

SIG2 = b"\x48\x89\x51\x08\x48\xc7\x41\x10"
thunks = []
i = 0
while i < TEXT_SZ - 22:
    if text[i] == 0xC7 and text[i+1] == 0x01:
        j = i + 6
        if text[j:j+8] == SIG2 and text[j+12] == 0xC3:
            thunks.append(TEXT_VA + i)
    i += 1
print(f"thunks: {len(thunks)}")

# search ALL sections (not just .rdata) for 8-byte pointers to thunks
tset = set(thunks)
for name, vaddr, raw, size in SECTS:
    if name == ".text":
        continue
    sblob = blob[raw:raw+size]
    hits = 0
    samples = []
    for k in range(0, len(sblob) - 8, 8):
        v = struct.unpack_from("<Q", sblob, k)[0]
        if v in tset:
            hits += 1
            if len(samples) < 5:
                samples.append(vaddr + k)
    print(f"{name}: {hits} pointer entries referencing thunks  {samples}")
