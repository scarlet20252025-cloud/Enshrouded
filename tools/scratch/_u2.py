import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
blob = open(r"C:\Windows\System32\ucrtbase.dll","rb").read()
off = 0x35280   # .text raw == VA
b = blob[off:off+0xC0]
for i in range(0, len(b), 16):
    chunk = b[i:i+16]
    print(f"{off+i:08x}  " + chunk.hex(' '))
print()
print("fault at 0x352c7 -> byte offset in this dump:", 0x352c7-0x35280)
print("logged instr bytes: 66 0F 7F 85 70 03 00 00 48 89 95 80 03 00 00 4C")
print("actual at 0x352c7:", blob[0x352c7:0x352c7+21].hex(' '))
