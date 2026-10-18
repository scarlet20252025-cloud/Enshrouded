r"""Disassemble 0x140954430 — the real event sender used by the tiny
SendEventEx wrappers (0x140954250 etc.).
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def dis(start, stop):
    r = subprocess.run([OBJ, "-d", "--start-address=" + start,
                        "--stop-address=" + stop, EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("%#x  %s" % (int(m.group(1), 16) - 0x140000000,
                                    m.group(3).strip()))
    return out


if __name__ == "__main__":
    for ln in dis("0x140954430", "0x140954800"):
        print(ln)
