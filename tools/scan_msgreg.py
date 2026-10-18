import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# Generic scan: any function that looks like
#   void RegThing(void* rcx /*out*/, void* rdx /*ctx*/) {
#       *(u32*)rcx = <hash>;
#       *(void**)(rcx+8) = rdx;
#       *(u64*)(rcx+0x10) = <size>;
#   }
# This is the "message registration" pattern seen at 0x140281A00 for PlayerInput.
# Report every site with its size, then reverse-lookup the hash.

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
REFL = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import json
by_qh = {t["qualifiedHash"]: t for t in json.load(open(REFL, encoding="utf-8"))["types"]}

blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

# C7 01 <imm32>  ; movl $hash,(%rcx)
# 48 89 51 08    ; movq %rdx,0x8(%rcx)
# 48 C7 41 10 <imm32> ; movq $size,0x10(%rcx)
# C3
SIG = b"\xc7\x01"
MID = b"\x48\x89\x51\x08\x48\xc7\x41\x10"
TAIL = b"\xc3"

sites = []
i = 0
n = len(text)
while i < n - 22:
    if text[i:i+2] == SIG:
        j = i + 6
        if text[j:j+len(MID)] == MID and text[j+len(MID)+4] == 0xC3:
            h = struct.unpack_from("<I", text, i+2)[0]
            sz = struct.unpack_from("<I", text, j+len(MID))[0]
            sites.append((TEXT_VA + i, h, sz))
    i += 1

print(f"message-registration sites: {len(sites)}")
known, unknown = [], []
for va, h, sz in sites:
    t = by_qh.get(h)
    if t:
        known.append((va, h, sz, t))
    else:
        unknown.append((va, h, sz))

print(f"known (in reflection table): {len(known)}   unknown: {len(unknown)}")
print()
print("=== known message registrations ===")
for va, h, sz, t in sorted(known, key=lambda x: x[0]):
    print(f"rva 0x{va:X}  qh=0x{h:08X}  size={sz:<5} {t['qualifiedName']}")
