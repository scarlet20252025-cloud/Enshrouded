import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
# .rdata VA 0x1413B0000 raw 0x13AEA00 size 0xC04CEE
rblob = blob[0x13AEA00:0x13AEA00+0xC04CEE]
RVA = 0x1413B0000
TEXT_LO, TEXT_HI = 0x140001000, 0x140001000+0x13AE480
cnt = 0
samples = []
for k in range(0, len(rblob)-8, 8):
    v = struct.unpack_from("<Q", rblob, k)[0]
    if TEXT_LO <= v < TEXT_HI:
        cnt += 1
        if v == 0x140281A00:
            print("FOUND PlayerInput thunk pointer at rva", hex(RVA+k))
        if len(samples) < 10:
            samples.append(hex(v))
print("rdata pointers into .text:", cnt)
print("samples:", samples)
