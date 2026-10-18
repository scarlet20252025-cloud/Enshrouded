"""Find the enclosing function and the register setup for a target RVA.

Scans backwards from `target` for a function prologue (int3 padding followed by
a push/sub, or `40 53`/`48 89 5C 24`), then disassembles-by-hex every write to a
named register inside that range so we can see where it came from.

Usage: python tools/trace_reg.py <targetRvaHex> <reg>   e.g. 2CB9AD r12
"""
import struct
import sys
from pathlib import Path

EXE = Path(r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe")

REGS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]


def sections(data):
    e = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e + 4
    nsec, = struct.unpack_from("<H", data, coff + 2)
    optsize, = struct.unpack_from("<H", data, coff + 16)
    opt = coff + 20
    out = []
    for i in range(nsec):
        o = opt + optsize + i * 40
        name = data[o:o + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        out.append((name, vaddr, vsize, rawptr, rawsize))
    return out


def main():
    target = int(sys.argv[1], 16)
    reg = sys.argv[2].lower()
    regidx = REGS.index(reg)
    data = EXE.read_bytes()
    secs = sections(data)
    _, tva, _, traw, trawsize = next(s for s in secs if s[0] == ".text")
    tstart = 0x1000

    def off(rva):
        return traw + (rva - tva)

    # find function start: walk back over int3 padding
    s = target
    while s > tstart + 16:
        if data[off(s - 1)] == 0xCC and data[off(s - 2)] == 0xCC:
            break
        s -= 1
    fn = s
    print(f"probable function start: 0x{fn:X}  (target 0x{target:X}, "
          f"{target - fn} bytes in)")

    # walk forward looking for writes to reg
    rva = fn
    end = target
    print(f"\nwrites to {reg} in 0x{fn:X}..0x{end:X}:")
    while rva < end:
        o = off(rva)
        b = data[o:o + 8]
        hit = None
        # REX.W / REX.R forms with reg in the low 3 bits of modrm.reg
        if b[0] in (0x48, 0x49, 0x4C, 0x4D) and b[1] in (0x89, 0x8B, 0x8D, 0x8C, 0x8E,
                                                        0x2B, 0x03, 0x0B, 0x13, 0x1B,
                                                        0x0F, 0x8D, 0x8E):
            modrm = b[2]
            mod = (modrm >> 6) & 3
            rm = modrm & 7
            r = (modrm >> 3) & 7
            ext = (b[0] & 1) << 3     # REX.B
            rex_r = (b[0] & 4) << 1   # REX.R -> bit 3
            regnum = r | rex_r
            if b[1] == 0x8D and regnum == regidx:
                # lea reg, [...]
                hit = f"lea {reg} <- mem"
            elif b[1] == 0x8B and regnum == regidx:
                hit = f"mov {reg} <- mem/reg"
            elif b[1] == 0x89 and (rm | ext) == regidx:
                hit = f"mov mem/reg <- {reg}"
            elif b[1] == 0x8C:
                hit = f"mov {reg} <- sreg"
        if hit:
            print(f"   0x{rva:X}: {b[:8].hex(' '):<24} {hit}")
        rva += 1


if __name__ == "__main__":
    main()
