import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
# PlayerInput thunk is rva 0x140281A00 -> file offset = 0x140281A00 - 0x140001000 + 0x400
off = 0x140281A00 - 0x140001000 + 0x400
print("file off of thunk:", hex(off))
print("bytes:", blob[off:off+20].hex(" "))
