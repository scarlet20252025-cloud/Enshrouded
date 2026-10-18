"""Resync-safe scan for stride arithmetic + indirect call in a byte window.

llvm-objdump does a linear sweep of the whole section, so any mid-instruction
start address desyncs everything after it. That is why several earlier
disassembly dumps looked like nonsense. Byte-level reads from the file are
authoritative; this tool scans a window byte-by-byte for the two patterns we
care about and prints the surrounding bytes so a human can verify alignment.

Usage: python tools/decode_window.py 0x99EF80 0x99F010
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common


def decode(b, start, end):
    """Yield (rva, kind, detail) for the patterns we track."""
    i = 0
    n = len(b)
    while i < n:
        rva = start + i
        op = b[i]
        # 48 69 /r imm32      imul r64, r/m64, imm32
        if op == 0x48 and i + 7 <= n and b[i + 1] == 0x69:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "imul64", "0x%X  modrm %02X" % (imm & 0xFFFFFFFF, b[i + 2]))
            i += 7
            continue
        # 4D 69 /r imm32      imul r8..r15, r/m64, imm32
        if op == 0x4D and i + 7 <= n and b[i + 1] == 0x69:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "imul64", "0x%X  modrm %02X" % (imm & 0xFFFFFFFF, b[i + 2]))
            i += 7
            continue
        # 48 81 /r imm32      add/or/and/adc/sbb/sub/xor/cmp r64, imm32
        if op == 0x48 and i + 7 <= n and b[i + 1] == 0x81:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "alu64", "op=%02X imm=0x%X" % (b[i + 2], imm & 0xFFFFFFFF))
            i += 7
            continue
        # 49 81 /r imm32
        if op == 0x49 and i + 7 <= n and b[i + 1] == 0x81:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "alu64", "op=%02X imm=0x%X" % (b[i + 2], imm & 0xFFFFFFFF))
            i += 7
            continue
        # 48 8D /r imm32      lea r64, [r64+imm32]
        if op == 0x48 and i + 7 <= n and b[i + 1] == 0x8D:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "lea64", "imm=0x%X" % (imm & 0xFFFFFFFF))
            i += 7
            continue
        # 49 8D /r imm32
        if op == 0x49 and i + 7 <= n and b[i + 1] == 0x8D:
            imm = struct.unpack_from("<i", b, i + 3)[0]
            yield (rva, "lea64", "imm=0x%X" % (imm & 0xFFFFFFFF))
            i += 7
            continue
        # FF /2 (mod=01) disp8  call [reg+disp8]
        if op == 0xFF and i + 3 <= n and (b[i + 1] & 0xC0) == 0x40:
            reg_field = (b[i + 1] >> 3) & 7
            if reg_field == 2:
                yield (rva, "callmem", "modrm %02X disp8 0x%02X" % (b[i + 1], b[i + 2]))
                i += 3
                continue
        # FF /2 (mod=11)       call reg
        if op == 0xFF and i + 2 <= n and (b[i + 1] & 0xC0) == 0xC0:
            if ((b[i + 1] >> 3) & 7) == 2:
                yield (rva, "callreg", "modrm %02X" % b[i + 1])
                i += 2
                continue
        # 41 FF .. (REX.B forms)
        if op == 0x41 and i + 3 <= n and b[i + 1] == 0xFF:
            modrm = b[i + 2]
            if (modrm & 0xC0) == 0x40 and ((modrm >> 3) & 7) == 2:
                yield (rva, "callmem", "REX modrm %02X disp8 0x%02X" % (modrm, b[i + 3]))
                i += 4
                continue
            if (modrm & 0xC0) == 0xC0 and ((modrm >> 3) & 7) == 2:
                yield (rva, "callreg", "REX modrm %02X" % modrm)
                i += 3
                continue
        i += 1


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    start = int(sys.argv[1], 0)
    end = int(sys.argv[2], 0)
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw = raw
            break
    b = data[traw + start:traw + end]
    for rva, kind, detail in decode(b, start, end):
        print("0x%08X  %-8s  %s" % (rva, kind, detail))
    return 0


if __name__ == "__main__":
    sys.exit(main())
