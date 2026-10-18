import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TARGETS = {0x140281A00: "PlayerInput thunk"}
# scan whole file for the 8-byte LE value anywhere (not just section-aligned)
for t, nm in TARGETS.items():
    pat = struct.pack("<Q", t)
    idx = 0
    found = []
    while True:
        i = blob.find(pat, idx)
        if i < 0: break
        found.append(i); idx = i+1
    print(nm, hex(t), "-> raw byte occurrences:", len(found), [hex(x) for x in found[:10]])
# also scan for rel32 that resolves: E8/E9 with disp reaching target from .text
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW+TEXT_SZ]
for t, nm in TARGETS.items():
    for op in (0xE8, 0xE9):
        i = 0
        cnt = 0
        while i < len(text)-5:
            if text[i]==op:
                disp = struct.unpack_from("<i", text, i+1)[0]
                if TEXT_VA+i+5+disp == t: cnt += 1
            i += 1
        print(f"{nm} rel32 {'call' if op==0xE8 else 'jmp'} sites: {cnt}")
