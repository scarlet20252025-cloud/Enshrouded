r"""Disassemble 0x12cf5c0..0x12cf6c0 using llvm-objdump directly (peek.py
hexrva needs a valid .text RVA; 0x12cf610 is inside .text so use objdump)."""
import subprocess
import sys

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % 0x14012CF5A0,
                        "--stop-address=%d" % 0x14012CF6C0, EXE],
                       capture_output=True, text=True, errors="replace")
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
