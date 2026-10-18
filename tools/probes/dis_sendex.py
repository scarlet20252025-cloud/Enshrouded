r"""Disassemble SendEventEx (0x140954250) to learn its true 5-arg signature.

Context: the tame handler at 0x47d761 calls it as
    rcx = GetCtx([rsi])            (world ctx)
    edx = *(u32*)(rbp-0x2e8)        (payload[0])
    r8d = *(u32*)(rbx+0x88)         (a field of the action record)
    r9d = 0
so we need to see which register is the type hash and which is the entity id,
and whether a size argument exists at all.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

START = "0x140954250"
STOP = "0x140954420"


def main():
    r = subprocess.run([OBJ, "-d", "--start-address=" + START,
                        "--stop-address=" + STOP, EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("%#x  %s" % (int(m.group(1), 16) - 0x140000000,
                                    m.group(3).strip()))
    print("\n".join(out))


if __name__ == "__main__":
    main()
