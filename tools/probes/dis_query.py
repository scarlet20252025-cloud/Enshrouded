r"""Disassemble 0x1409BAB60 with correct alignment to recover the query-begin
signature (it is an ECS query builder used by wildlife_enemy_transformer).

Strategy: disassemble from several candidate starts and pick the one that yields
sane code, then print the tail where the output buffer is filled.
"""
import subprocess

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

for start in (0x1409BAB60, 0x1409BAB50, 0x1409BAB40):
    r = subprocess.run([OBJDUMP, "-d", "--section=.text",
                        "--start-address=%d" % start,
                        "--stop-address=%d" % (start + 0xC0), EXE],
                       capture_output=True, text=True, errors="replace")
    print("=== start=%#x" % start)
    print(r.stdout or "")


if __name__ == "__main__":
    pass
