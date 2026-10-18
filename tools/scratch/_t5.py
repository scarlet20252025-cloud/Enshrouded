import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]
SIG2 = b"\x48\x89\x51\x08\x48\xc7\x41\x10"
print("SIG2 len:", len(SIG2), "hex:", SIG2.hex(" "))
idx = 0x280a00
j = idx + 6
print("text[j:j+7]:", text[j:j+7].hex(" "))
print("text[j+11]:", hex(text[j+11]))
print("equal:", text[j:j+7] == SIG2, text[j+11] == 0xC3)
