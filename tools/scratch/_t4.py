import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]
idx = 0x280e00 - 0x400
print("text[idx] =", hex(text[idx]))
print("expected c7")
print("idx calc:", hex(idx), "TEXT_SZ:", hex(TEXT_SZ))
print("slice:", text[idx:idx+8].hex(" "))
