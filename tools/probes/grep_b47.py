r"""The 4 hits for u32 2887 in .text are mostly false positives (misaligned
instruction bytes). Verify each by checking whether the 4 bytes at the site are
actually an instruction immediate: re-disassemble with llvm-objdump and look for
`$0xb47`.

Better: use llvm-objdump's own output and grep for 0xb47.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJ, "-d", "--section=.text", EXE],
                       capture_output=True, text=True, errors="replace")
    out = r.stdout or ""
    print("disassembly chars:", len(out))
    hits = []
    for ln in out.splitlines():
        if "0xb47" in ln or "$2887" in ln:
            hits.append(ln.strip())
    print("lines mentioning 0xb47/$2887:", len(hits))
    for h in hits[:40]:
        print("   " + h)


if __name__ == "__main__":
    main()
