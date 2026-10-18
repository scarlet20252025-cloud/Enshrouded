r"""Definitive disassembly of Enqueue (0x140952400).

We need the exact record layout because SendEventEx (0x140954250) — the
function the TameWildlifeEvent path calls — writes only 4 bytes into the
record (record+0xC = target entity id) with size=0x10, flags=1.
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
    for ln in dis("0x140952400", "0x140952640"):
        print(ln)
