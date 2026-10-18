r"""Extract the immediate hash constants compared inside 0x47fc97.

Print every `cmpq $0x...` in raw form with the FULL 8-byte displacement, since
objdump truncates some. Use our own decoder so we can see the actual 32/64-bit
immediates that encode the message type hashes.
"""
import re
import subprocess
import sys

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % 0x14047FC97,
                        "--stop-address=%d" % 0x140480400, EXE],
                       capture_output=True, text=True, errors="replace")
    text = r.stdout or r.stderr
    for ln in text.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$", ln)
        if not m:
            continue
        insn = m.group(3).strip()
        # Show the raw bytes for any compare against an immediate.
        if re.match(r"^cmp", insn):
            print("%s  %-46s  %s" % (m.group(1), m.group(2).strip(), insn))


if __name__ == "__main__":
    main()
