import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]

# Same instruction-shape as SetIsTame but any hash, generic opcode scan:
#   C7 40 0C <imm32>   movl $imm32, 0xc(%rax)
#   66 C7 40 4C 01 00  movw $1, 0x4c(%rax)
#   0F B6 03           movzbl (%rbx), %eax
#   88 41 6C           movb %al, 0x6c(%rcx)
# We know SetIsTame has 0 direct callers, so find all sites of the
# 19-byte body and report each hash + containing function start.

PATTERN_LEN = 19
sig = b"\xc7\x40\x0c"
sig2 = b"\x66\xc7\x40\x4c\x01\x00\x0f\xb6\x03\x88\x41\x6c"

sites = []
i = 0
n = len(text)
while i < n - PATTERN_LEN:
    if text[i:i+3] == sig and text[i+7:i+19] == sig2:
        h = struct.unpack_from("<I", text, i+3)[0]
        sites.append((TEXT_VA + i, h))
    i += 1

print(f"raw pattern sites: {len(sites)}")
for va, h in sites:
    print(f"  rva 0x{va:X}  hash 0x{h:08X}")
