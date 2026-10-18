r"""Dump the full function containing the tame handler at rva 0x47d5bc.

The .pdata entry starts at 0x47d5bc, but the real prologue is earlier: the
handler clearly continues past 0x47d7c3. Find the enclosing function via
.pdata, then disassemble the whole thing so the tame branch can be read in
context (what rbx/rsi/r15 point at, and where the loop's descriptor array
comes from).
"""
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def dis(va, n):
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % va,
                        "--stop-address=%d" % (va + n), EXE],
                       capture_output=True, text=True, errors="replace")
    return (r.stdout or r.stderr).splitlines()


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    va = S.IMAGE_BASE + 0x47D5BC
    r = S.enclosing(funcs, va)
    print("enclosing func: %s" % (r,))
    if not r:
        return
    b, e = r
    size = e - b
    print("func rva=%#x size=%d" % (b - S.IMAGE_BASE, size))
    lines = dis(b, size)
    # Print everything from the start through 0x14047d7c3.
    out = []
    for ln in lines:
        if ln.startswith("14047d5") or ln.startswith("14047d6") or ln.startswith("14047d7"):
            out.append(ln)
    print("\n".join(out[:200]))


if __name__ == "__main__":
    main()
