# -*- coding: utf-8 -*-
"""Log the message type hash for every SendEvent call by matching FNV-1a.

All Enqueue calls carry the component hash, so we can name them from the
reflection table.  Do the same for SendEvent, which carries typeHash in r8d.
For SendEvent the word at (%rbx) holds the hash, so read 4 bytes at +0.

Then dump the payload's first 24 bytes so we can learn the real layout.
"""
import io
import struct
import subprocess

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"

IMAGE_BASE = 0x140000000
TEXT_VA = 0x140001000
TEXT_RAW = 0x400
TEXT_SIZE = 0x13AE480

RVA = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x955400
COUNT = int(sys.argv[2], 0) if len(sys.argv) > 2 else 0x150


def va_to_off(va):
    return va - TEXT_VA + TEXT_RAW


def main():
    start_va = IMAGE_BASE + RVA
    off = va_to_off(start_va)
    cmd = [
        OBJ, "--disassemble",
        "--start-address=%#x" % start_va,
        "--stop-address=%#x" % (start_va + COUNT),
        "--no-show-raw-insn",
        EXE,
    ]
    out = subprocess.run(cmd, capture_output=True, text=True)
    lines = out.stdout.splitlines()
    keep = []
    for ln in lines:
        if ln.strip().startswith("140955400"):
            keep.append(ln)
    print("\n".join(keep[:200]))


if __name__ == "__main__":
    main()
