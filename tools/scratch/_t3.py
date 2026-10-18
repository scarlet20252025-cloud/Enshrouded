import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
off = 0x280e00
b = blob[off:off+20]
print("expected:", b.hex(" "))
print("text slice check:")
text = blob[0x400:0x400+0x13AE480]
print(text[off-0x400:off-0x400+20].hex(" "))
print("match:", text[off-0x400:off-0x400+20] == b)
