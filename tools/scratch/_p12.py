import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()

# --- what is 0x6BA7F22A ? ---
import json
d = json.load(open(r"tools\kfc\reflection_data.json", encoding="utf-8"))
want = {0x6BA7F22A: "0x6BA7F22A"}
for t in d["types"]:
    if t["qualifiedHash"] in want:
        print(f"{want[t['qualifiedHash']]} = {t['qualifiedName']} idx={t['index']} size={t['size']}")

# --- correct .pdata walk ---
RAW = 0x2160A00
lo, hi = 0x1000, 0x13AE480 + 0x1000
entries = []
for i in range((len(data)-RAW)//12):
    b,e,u = struct.unpack_from("<III", data, RAW+i*12)
    if lo <= b < hi and lo < e <= hi and b < e:
        entries.append((b,e,u))
entries.sort()
print(f"\npdata entries parsed: {len(entries)}")
target = 0x2CB9E6
for b,e,u in entries:
    if b <= target < e:
        print(f"FUNCTION containing 0x{target:X}: 0x{b:X} .. 0x{e:X}  size 0x{e-b:X}")
