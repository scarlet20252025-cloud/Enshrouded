r"""TameWildlifeEvent is compared at 0x47d718 inside func 0x47d5bc..0x47d7fd.
That looks like a dispatch/compare site, not a submit. Disassemble the whole
function to see what it is: it may be the actual tame handler, which is the
real backend the console needs.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJ, "-d",
                        "--start-address=0x14047D5BC",
                        "--stop-address=0x14047D7FD", EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("  %#x  %s" % (int(m.group(1), 16) - 0x140000000,
                                      m.group(3).strip()))
    print("\n".join(out))


if __name__ == "__main__":
    main()
