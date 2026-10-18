import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p, "rb").read()
RAW, SIZE = 0x2160A00, 0xD4FC4
n = (len(data) - RAW) // 12
target = 0x2CB9E6
for i in range(n):
    b, e, u = struct.unpack_from("<III", data, RAW + i*12)
    if b <= target < e:
        print(f"containing rva 0x{target:X}: begin=0x{b:X} end=0x{e:X} size=0x{e-b:X} unwind=0x{u:X}")
print("\n-- neighbours --")
for i in range(n):
    b, e, u = struct.unpack_from("<III", data, RAW + i*12)
    if 0x2CA000 <= b <= 0x2CE000:
        print(f"  0x{b:X} .. 0x{e:X}  (size 0x{e-b:X})")
