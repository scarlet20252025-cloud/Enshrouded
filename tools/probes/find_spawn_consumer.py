r"""Find who consumes the 24-byte-descriptor array built by the spawn-pack
function 0x140221280.

The Faction site 0x222861 writes into rbp+0x16618 (a stack-allocated copy of
the faction byte) and appends {hash,ptr,size} to the array at rbp+0xf0.
That array must be handed to a spawner. Search the function's tail for the
call that passes rbp+0xf0 (the array head) as an argument.

Instead of disassembling 8264 bytes by eye, dump the whole function to a file
and grep for the offsets 0xf0(%rbp) / 0x16618(%rbp) to find the consumer.
"""
import re
import subprocess
import sys

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

START = 0x140221280
STOP = 0x1402231C8        # 0x140221280 + 8264


def dis(start, stop):
    r = subprocess.run([OBJ, "-d", "--start-address=%#x" % start,
                        "--stop-address=%#x" % stop, EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("%#x\t%s" % (int(m.group(1), 16) - 0x140000000,
                                     m.group(3).strip()))
    return out


def main():
    lines = dis(START, STOP)
    print("function 0x140221280 .. %#x  (%d insns)" % (STOP, len(lines)))
    print()
    print("--- references to the descriptor array at rbp+0xf0 ---")
    for ln in lines:
        if re.search(r"0xf0\(%rbp\)", ln):
            print(" ", ln)
    print()
    print("--- references to the Faction byte copy at rbp+0x16618 ---")
    for ln in lines:
        if re.search(r"0x16618\(%rbp\)", ln):
            print(" ", ln)
    print()
    print("--- all direct calls ---")
    for ln in lines:
        if "\tcallq\t" in ln:
            print(" ", ln)


if __name__ == "__main__":
    main()
