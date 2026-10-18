r"""Disassemble 0x1402139b0 -- the function the tame handler calls to build the
descriptor array that it then walks looking for hash 0x537B675C.

If this is a generic "collect components matching these tags" helper, then the
whole tame path is: gather the entity's Animal components -> find TameWildlifeEvent
-> ResolveEnt -> SendEventEx(ctx, ?, eid).
"""
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    va = S.IMAGE_BASE + 0x2139B0
    r = S.enclosing(funcs, va)
    print("enclosing: %s" % (r,))
    if not r:
        return
    b, e = r
    size = min(e - b, 900)
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % b,
                        "--stop-address=%d" % (b + size), EXE],
                       capture_output=True, text=True, errors="replace")
    print((r.stdout or r.stderr))


if __name__ == "__main__":
    main()
