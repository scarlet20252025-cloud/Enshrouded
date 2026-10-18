r"""Find the hash->handler dispatch table used by 0x47fc97.

The tame handler is called from 0x47feb1 unconditionally after a `cmpb` guard
chain, meaning the enclosing block IS the TameWildlifeEvent branch. Walk the
disassembly from 0x47fc97 collecting every `cmpq $imm32` and every
`callq <imm>` whose target is a local helper, to reconstruct the branch order.
"""
import re
import struct
import subprocess
import sys

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

START, STOP = 0x14047FC97, 0x140480350


def main():
    r = subprocess.run([OBJDUMP, "-d", "--start-address=%d" % START,
                        "--stop-address=%d" % STOP, EXE],
                       capture_output=True, text=True, errors="replace")
    text = r.stdout or r.stderr
    lines = text.splitlines()
    # Print only hash comparisons and their surrounding target blocks.
    keep = []
    for i, ln in enumerate(lines):
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if not m:
            continue
        insn = m.group(3).strip()
        if re.match(r"^(cmpq|cmpb|cmpl|cmps|cmp)\s+\$0x[0-9a-f]+", insn):
            keep.append("CMP  %s  %s" % (m.group(1), insn))
        elif re.match(r"^callq\s+0x", insn):
            keep.append("CALL %s  %s" % (m.group(1), insn))
        elif re.match(r"^(jne|je|ja|jae|jb|jbe|jmp)\s", insn):
            keep.append("JMP  %s  %s" % (m.group(1), insn))
    print("\n".join(keep))


if __name__ == "__main__":
    main()
