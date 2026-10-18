import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
byhash = {t["qualifiedHash"]: t for t in d["types"]}
# scan the .text region 0x2CB8C0..0x2CCC00 for BA imm32 (mov edx,imm) and C7 44 CD 60 imm32 (collector push)
lo, hi = 0x2CB000, 0x2CD000
raw = lambda rva: 0x400 + (rva - 0x1000)
seen = {}
for rva in range(lo, hi-8):
    o = raw(rva)
    # pattern: c7 44 cd 60 <imm32>
    if data[o:o+3] == b"\xc7\x44\xcd" :
        imm, = struct.unpack_from("<I", data, o+4)
        seen.setdefault(imm, []).append(rva)
    # pattern: c7 44 d5 60 (rbp,rdx,8)
    if data[o:o+3] == b"\xc7\x44\xd5" :
        imm, = struct.unpack_from("<I", data, o+4)
        seen.setdefault(imm, []).append(rva)
print("collected event hashes in 0x2CB000..0x2CD000:")
for h, sites in sorted(seen.items(), key=lambda kv: -len(kv[1])):
    t = byhash.get(h)
    print(f"  0x{h:08X}  x{len(sites):<3} {t['qualifiedName'] if t else '<unknown>'}  first@rva 0x{sites[0]:X}")
