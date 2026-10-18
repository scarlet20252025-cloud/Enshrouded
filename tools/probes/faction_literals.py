r"""Find the 4-byte literal Faction hash 0xA1F30F21 in the RAW file and check
whether it is near a call to Enqueue (0x140952400 -> rel32) in .text.

If the game itself never enqueues Faction, the Enqueue channel is closed for
it. If it does, we learn the exact record shape to copy.
"""
import re
import struct
import subprocess

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"


def main():
    data = open(EXE, "rb").read()
    needle = struct.pack("<I", 0xA1F30F21)
    off = 0
    hits = []
    while True:
        i = data.find(needle, off)
        if i < 0:
            break
        hits.append(i)
        off = i + 1
    print("Faction hash 0xA1F30F21 occurs %d times in the file" % len(hits))
    for h in hits:
        # Convert file offset to RVA via the known segment table:
        #   .text : raw 0x400    va 0x140001000
        #   .rdata: raw 0x13AEA00 va 0x14013B0000
        #   .data : raw 0x1FCEA00 va 0x1401FB5000
        if 0x13AEA00 <= h < 0x1FCEA00:
            rva = h + 0x14013B0000 - 0x13AEA00
            seg = ".rdata"
        elif 0x400 <= h < 0x13AEA00:
            rva = h + 0x140001000 - 0x400
            seg = ".text"
        elif 0x1FCEA00 <= h < 0x1FCEA00 + 0x1B200:
            rva = h + 0x1401FB5000 - 0x1FCEA00
            seg = ".data"
        else:
            rva, seg = 0, "?"
        print("  file %#-9x  %s rva %#x" % (h, seg, rva))


if __name__ == "__main__":
    main()
