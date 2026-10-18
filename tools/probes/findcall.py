import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

def find_calls(target_va):
    out = []
    i = 0
    n = len(text)
    while i < n - 5:
        if text[i] == 0xE8:
            rel = struct.unpack_from("<i", text, i + 1)[0]
            src_va = TEXT_VA + i
            if src_va + 5 + rel == target_va:
                out.append(src_va)
        i += 1
    return out

targets = {
    "SetIsTame":            0x14047D040,
    "SendEvent":            0x140955400,
    "SendEventEx(0x140954250)": 0x140954250,
    "Enqueue(0x140952400)": 0x140952400,
    "GetEntityId(0x1409b6a20)": 0x1409B6A20,
    "GetEventBuf(0x1409b85d0)": 0x1409B85D0,
    "ResolveEnt(0x1409b2e40)": 0x1409B2E40,
    "0x1409b0860":          0x1409B0860,
    "0x1409b8030":          0x1409B8030,
}

for name, va in targets.items():
    sites = find_calls(va)
    rs = " ".join(f"0x{r:X}" for r in sites[:20])
    more = "" if len(sites) <= 20 else f" (+{len(sites)-20} more)"
    print(f"{name:28s} {len(sites):5d} call sites: {rs}{more}")
