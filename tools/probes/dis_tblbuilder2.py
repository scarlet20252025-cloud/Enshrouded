r"""objdump's --start-address needs an address in the loaded image; try with the
absolute address form 0x14012cf5c0 (already tried) but with --section .text."""
import subprocess

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

for start in (0x14012CF5A0, 0x14012CF5C0, 0x14012CF600):
    r = subprocess.run([OBJDUMP, "-d", "--section=.text",
                        "--start-address=%d" % start,
                        "--stop-address=%d" % (start + 0x60), EXE],
                       capture_output=True, text=True, errors="replace")
    print("=== start=%#x rc=%d" % (start, r.returncode))
    print((r.stdout or "")[-2000:])
    print((r.stderr or "")[-500:])
