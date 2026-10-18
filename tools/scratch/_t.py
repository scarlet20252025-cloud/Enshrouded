import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]
# thunk = C7 01 <hash> | 48 89 51 08 | 48 C7 41 10 <size> | C3
thunks = []
i = 0
while i < TEXT_SZ - 22:
    if text[i] == 0xC7 and text[i+1] == 0x01:
        j = i + 6
        if text[j:j+7] == b"\x48\x89\x51\x08\x48\xc7\x41\x10" and text[j+11] == 0xC3:
            thunks.append(TEXT_VA + i)
    i += 1
print("thunks found:", len(thunks))
print("first 5:", [hex(t) for t in thunks[:5]])
