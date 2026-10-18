r"""Generic function/range disassembler.

Usage:
    python dis.py 0x480C70                       # one function
    python dis.py 0x480C70 0x481060              # range
    python dis.py -site 0x222861                 # one call site +-0x30 bytes
"""
import re
import subprocess
import sys

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def dis(start, stop):
    r = subprocess.run([OBJ, "-d", "--start-address=%#x" % start,
                        "--stop-address=%#x" % stop, EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("%#-9x %s" % (int(m.group(1), 16) - 0x140000000,
                                     m.group(3).strip()))
    return out


def main(argv):
    if not argv:
        print(__doc__)
        return
    if argv[0] == "-site":
        a = int(argv[1], 16)
        for ln in dis(a - 0x30, a + 0x40):
            print(ln)
        return
    if len(argv) == 1:
        a = int(argv[0], 16)
        for ln in dis(a, a + 0x200):
            print(ln)
        return
    a, b = int(argv[0], 16), int(argv[1], 16)
    for ln in dis(a, b):
        print(ln)


if __name__ == "__main__":
    main(sys.argv[1:])
