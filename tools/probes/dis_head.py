r"""Print the head of 0x47fc97 including the first compares we filtered out."""
import subprocess
import sys

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % 0x14047FC97,
                        "--stop-address=%d" % 0x14047FD00, EXE],
                       capture_output=True, text=True, errors="replace")
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
