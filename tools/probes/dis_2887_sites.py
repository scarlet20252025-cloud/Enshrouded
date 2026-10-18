r"""Investigate the 4 sites that reference reflection index 2887 (AdminSpawnCommand).
Print 40 bytes of disassembly context around each.
"""
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
SITES = [0x165E80, 0x72A320, 0x8526E0, 0x1248D50]


def main():
    for s in SITES:
        print("=" * 74)
        print("site rva=%#x" % s)
        r = subprocess.run([OBJ, "-d", "--start-address=%d" % (0x140000000 + s),
                            "--stop-address=%d" % (0x140000000 + s + 0x50), EXE],
                           capture_output=True, text=True, errors="replace")
        for ln in (r.stdout or "").splitlines():
            if ln.startswith("0000") or (ln[:2].isdigit() is False and ":" in ln):
                pass
            if ":\t" in ln or "   \t" in ln:
                print(ln)
        print()


if __name__ == "__main__":
    main()
