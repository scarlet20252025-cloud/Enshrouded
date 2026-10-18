r"""Full disassembly of wildlife_enemy_transformer handler 0x140480c70 so we can
decide whether calling it directly on a wolf entity performs the enemy->wildlife
transformation (the key to making a wolf tameable).
"""
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJ, "-d",
                        "--start-address=%d" % 0x140480C70,
                        "--stop-address=%d" % 0x140481055, EXE],
                       capture_output=True, text=True, errors="replace")
    for ln in (r.stdout or "").splitlines():
        if ":\t" in ln:
            print(ln.split("\t", 1)[1] if "\t" in ln else ln)


if __name__ == "__main__":
    main()
