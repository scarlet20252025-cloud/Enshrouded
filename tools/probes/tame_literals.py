r"""Where is TameWildlifeEvent SENT from? We only ever found the consumer
comparison at 0x47d718. Search the whole file for the 4-byte literal and map
each hit to a segment + RVA, then disassemble the surrounding function of any
.text hit that is NOT 0x47d718.
"""
import struct

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
HASH = 0x537B675C

SEGS = [
    (0x400, 0x13AEA00, 0x140001000 - 0x400, ".text"),
    (0x13AEA00, 0x1FCEA00, 0x14013B0000 - 0x13AEA00, ".rdata"),
    (0x1FCEA00, 0x1FCEA00 + 0x1B200, 0x1401FB5000 - 0x1FCEA00, ".data"),
    (0x1FCFC00, 0x2AA4000, 0x1402836000 - 0x1FCEA00, ".pdata"),
]


def to_rva(h):
    for lo, hi, delta, name in SEGS:
        if lo <= h < hi:
            return h + delta, name
    return 0, "?"


def main():
    data = open(EXE, "rb").read()
    needle = struct.pack("<I", HASH)
    off = 0
    n = 0
    while True:
        i = data.find(needle, off)
        if i < 0:
            break
        n += 1
        rva, seg = to_rva(i)
        print("  file %#-9x %-7s rva %#x" % (i, seg, rva))
        off = i + 1
    print("TameWildlifeEvent hash 0x537B675C occurs %d times" % n)


if __name__ == "__main__":
    main()
