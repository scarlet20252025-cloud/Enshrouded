import sys, io, struct, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
raw = lambda rva: 0x400 + (rva - 0x1000)
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
byhash = {t["qualifiedHash"]: t for t in d["types"]}

lo, hi = 0x2C0000, 0x2D4000
# reads of the (hash,ptr,size) array: mov 0x68(%rbp,%rcx,8) / 0x70(..)
pats = {
  "read_ptr  (48 8b 44 cd 68)": b"\x48\x8b\x44\xcd\x68",
  "read_size (48 8b 4c cd 70)": b"\x48\x8b\x4c\xcd\x70",
  "read_ptr2 (48 8b 44 d5 68)": b"\x48\x8b\x44\xd5\x68",
}
for label, pat in pats.items():
    hits=[]
    for rva in range(lo, hi):
        if data[raw(rva):raw(rva)+len(pat)] == pat:
            hits.append(rva)
    print(f"{label}: {len(hits)} hits -> {[hex(h) for h in hits[:12]]}")
