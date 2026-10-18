import sys, io, struct
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
blob = open(EXE, "rb").read()
TEXT_RAW, TEXT_VA, TEXT_SZ = 0x400, 0x140001000, 0x13AE480
text = blob[TEXT_RAW:TEXT_RAW + TEXT_SZ]
TARGET = 0x140281A00
# any RIP-relative displacement encoding: opcode byte, modrm=00rrr101 (mod=00, rm=101)
# possible opcodes with disp32 following: 48 8d 05 etc (lea), or any op with /r
# brute: scan for modrm byte of form 0x05,0x0d,0x15,0x1d,0x25,0x2d,0x35,0x3d
# preceded by any byte, and check next insn addr == TARGET
n = len(text)
found = []
for i in range(1, n - 8):
    if text[i] in (0x05,0x0d,0x15,0x1d,0x25,0x2d,0x35,0x3d):
        # candidate rip-relative disp starts at i+1
        if i + 5 > n: break
        disp = struct.unpack_from("<i", text, i+1)[0]
        insn_va = TEXT_VA + i - 1   # assume opcode at i-1
        if insn_va + 7 + disp == TARGET or TEXT_VA + i + 1 + 7 + disp == TARGET:
            found.append((TEXT_VA + i, text[i-1], disp))
print("candidates:", len(found))
for va, op, disp in found[:40]:
    print(f"  rva 0x{va:X} opcode=0x{op:02X} disp=0x{disp & 0xFFFFFFFF:08X}")
