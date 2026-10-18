r"""Only 2 occurrences: the .text consumer at 0x14047d71a and an .rdata data
pointer at 0x1401b01110. Check what .rdata entry references that pointer —
if it is a dispatch table we may hook it; if it is a name string table, the
hash is only used for comparison.

Also: what is at 0x14047d71a's function (0x14047d5bc)? Is it called by address
from anywhere? Find its callers by scanning for rel32 calls targeting it.
"""
import re
import struct
import subprocess

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"

TARGET_RVA = 0x47d5bc


def main():
    data = open(EXE, "rb").read()
    # raw file offset of the .rdata occurrence
    off = 0x1affb10
    # print the 32 bytes around it as qwords + guesses
    chunk = data[off - 32: off + 32]
    q = struct.unpack("<8Q", chunk)
    for i, v in enumerate(q):
        print("  qw [%#x] = %#018x" % (0x1401b01110 - 32 + i * 8, v))

    # Who references rva 0x1401b01110?
    print()
    print("--- code/data referencing rva 0x1401b01110 ---")
    needle = struct.pack("<Q", 0x1401b01110)
    o = 0
    n = 0
    while True:
        i = data.find(needle, o)
        if i < 0:
            break
        n += 1
        rva = i + 0x14013B0000 - 0x13AEA00 if i >= 0x13AEA00 else i + 0x140001000 - 0x400
        print("  file %#-9x rva %#x" % (i, rva))
        o = i + 1
    print("  total %d" % n)


if __name__ == "__main__":
    main()
