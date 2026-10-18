r"""The 123 `callq *0x28(%rax)` sites include many virtual calls unrelated to
the program dispatcher. Narrow it: the ECS program slots live at
world+0x746350 (stride 0x1f20). A dispatcher that walks that table must index it,
i.e. it must contain `imul $0x1f20` or `lea` with 0x746350/0x746360.

Search the full disassembly for those constants.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

WANT = ["0x1f20", "0x746350", "0x746360", "0x746380"]


def main():
    r = subprocess.run([OBJ, "-d", "--section=.text", EXE],
                       capture_output=True, text=True, errors="replace")
    lines = (r.stdout or "").splitlines()
    print("lines:", len(lines))
    for i, ln in enumerate(lines):
        for w in WANT:
            if w in ln:
                print("%6d  %s" % (i, ln.strip()))
                break


if __name__ == "__main__":
    main()
