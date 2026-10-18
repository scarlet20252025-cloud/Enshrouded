import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

d = json.load(open(REFL, encoding="utf-8"))
types = d["types"]
by_qh = {t["qualifiedHash"]: t for t in types}

blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

# Generic component-setter shape:
#   C7 40 0C <imm32>   movl $typeHash, 0xc(%rax)
#   66 C7 40 XX 01 00  movw $1, 0x??(%rax)      <- data offset of the component field (varies)
#   0F B6 03           movzbl (%rbx), %eax
#   88 41 YY           movb %al, 0x??(%rcx)
#
# Scan for C7 40 0C <hash> followed by 66 C7 40 within 12 bytes.

def find_sites():
    out = []
    i = 0
    n = len(text)
    while i < n - 24:
        if text[i] == 0xC7 and text[i+1] == 0x40 and text[i+2] == 0x0C:
            h = struct.unpack_from("<I", text, i+3)[0]
            # look for 66 C7 40 in next 12 bytes
            j = i + 7
            end = min(i + 24, n - 7)
            while j < end:
                if text[j] == 0x66 and text[j+1] == 0xC7 and text[j+2] == 0x40:
                    off = text[j+3]
                    val = struct.unpack_from("<H", text, j+4)[0]
                    if val == 1:
                        out.append((TEXT_VA + i, h, off))
                        break
                j += 1
        i += 1
    return out

sites = find_sites()
print(f"generic component-setter sites: {len(sites)}")
print()
seen = {}
for va, h, off in sites:
    t = by_qh.get(h)
    name = t["qualifiedName"] if t else f"<unknown {h:08X}>"
    idx = t["index"] if t else -1
    size = t["size"] if t else 0
    seen.setdefault(h, []).append((va, off))
    print(f"rva 0x{va:X}  qh=0x{h:08X}  dataoff=0x{off:02X}  idx={idx:<6} size={size:<6} {name}")

print()
print(f"distinct component types with setters: {len(seen)}")
