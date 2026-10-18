r"""Locate the dispatch table that maps message-hash -> handler.

0x47fc97 is the ONLY caller of the tame handler (0x47d560). It is a small
dispatcher that also calls 0x47d460. Disassemble it fully to see how the hash
selects the handler, then find the table it indexes so we can register our own
message type (e.g. a custom "WolfCommand" message) and get a native dispatch
slot for free.
"""
import subprocess
import sys

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % (0x14047FC97),
                        "--stop-address=%d" % (0x140480330), EXE],
                       capture_output=True, text=True, errors="replace")
    print(r.stdout or r.stderr)


if __name__ == "__main__":
    main()
