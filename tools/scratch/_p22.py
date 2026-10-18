import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
p = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
data = open(p,"rb").read()
raw = lambda rva: 0x400 + (rva - 0x1000)
lo, hi = 0x2CCB00, 0x2CE400
# Look for calls to Enqueue 0x952400 within this function, and calls with edx = rbp+0x60 base
for rva in range(lo, hi-5):
    if data[raw(rva)] == 0xE8:
        rel, = struct.unpack_from("<i", data, raw(rva)+1)
        tgt = rva + 5 + rel
        if 0x950000 <= tgt <= 0x956000:
            print(f"call @ rva 0x{rva:X} -> 0x{tgt:X}")
print("\n--- lea rdx/rsi referencing 0x60(%rbp) near end ---")
for rva in range(lo, hi-8):
    o = raw(rva)
    if data[o:o+4] == b"\x48\x8d\x95" or data[o:o+4] == b"\x48\x8d\xb5":
        disp, = struct.unpack_from("<i", data, o+4)
        if 0x40 <= disp <= 0x400:
            print(f"  rva 0x{rva:X}  lea disp=0x{disp:X}(%rbp)")
