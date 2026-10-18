import json, sys, io, struct, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

d = json.load(open(REFL, encoding="utf-8"))
types = d["types"]
by_qh = {}
for t in types:
    by_qh[t["qualifiedHash"]] = t

# sections
SECTIONS = [
    (".text",  0x140001000, 0x400, 0x13AE480),
    (".rdata", 0x1413B0000, 0x13AEA00, 0xC04CEE),
    (".data",  0x141FB5000, 0x1FAEA00, 0x1B200),
    (".pdata", 0x142836000, 0x14295E000 - 0x142836000, 0xD4FC4),
]

blob = open(EXE, "rb").read()
text_raw, text_va, text_sz = 0x400, 0x140001000, 0x13AE480
text = blob[text_raw:text_raw + text_sz]

# Pattern: movl $imm32, 0xc(%rax)   => C7 40 0C xx xx xx xx
# followed (within 16 bytes) by movw $1, 0x4c(%rax) => 66 C7 40 4C 01 00
# then movzbl (%rbx),%eax ; movb %al,0x6c(%rcx)
pat = re.compile(rb"\xc7\x40\x0c(....)\x66\xc7\x40\x4c\x01\x00\x0f\xb6\x03\x88\x41\x6c", re.S)

found = {}
for m in pat.finditer(text):
    h = struct.unpack("<I", m.group(1))[0]
    rva = text_va + m.start()
    t = by_qh.get(h)
    found.setdefault(h, []).append(rva)

print(f"component-setter pattern found: {sum(len(v) for v in found.values())} sites, {len(found)} distinct hashes")
print()
rows = []
for h, rvas in sorted(found.items(), key=lambda kv: kv[1][0]):
    t = by_qh.get(h)
    if t:
        rows.append((t["qualifiedName"], t["index"], t["size"], h, rvas))
    else:
        rows.append((f"<unknown {h:08X}>", -1, 0, h, rvas))

for name, idx, size, h, rvas in rows:
    rs = " ".join(f"0x{r:X}" for r in rvas[:6])
    more = "" if len(rvas) <= 6 else f" (+{len(rvas)-6})"
    print(f"idx={idx:<6} size={size:<6} qh={h:08X} {name:<55} {rs}{more}")
