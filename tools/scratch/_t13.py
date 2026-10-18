import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
for t in (0x140281A00, 0x1402819C0, 0x140212F00, 0x14021D470):
    p8 = struct.pack("<Q", t)
    p4 = struct.pack("<I", t & 0xFFFFFFFF)
    print(hex(t), "u64 count:", blob.count(p8), "u32(low) count:", blob.count(p4))
