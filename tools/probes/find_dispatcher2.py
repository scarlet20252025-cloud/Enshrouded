r"""Find the ECS program dispatcher: the code that loads slot+0x28 (the handler)
from the program table at world+0x746350 (stride 0x1f20) and calls it.

A dispatcher must, in the same basic block or within a few instructions:
  - reference 0x746350 / 0x746360 (the slot table base), OR use imul $0x1f20
  - load offset 0x28 from the slot
  - call through it

We already know the only code touching 0x746350/0x1f20 besides the registrar
is at 0x140A17A33 (which only sets bitsets). So the dispatcher probably uses
a DIFFERENT base — the program table might be reachable through a pointer
stored elsewhere (e.g. world+0x746358 holds slotBase).

Better approach: the handler address 0x140480C70 must appear somewhere as the
TARGET of an indirect call. We cannot see indirect targets in a static dump.
BUT the registrar copies descriptor->handler into slot+0x28, and descriptors
are reached through the 16 thunks at 0x12CF5C0. So the table is populated by
0x1404a5a30 (the bootstrap).

So the ONLY way to reach a handler is the dispatcher. Let's find it by looking
for code that indexes the table with a program INDEX. The registrar stores
`slot+0x8 = index` (u16) at 0x1409d59cd. A dispatcher would read a u16 index
and multiply by 0x1f20.

Search for `movzwl` + `imul $0x1f20` proximity, or any `imul $0x1f20` we have
not yet explained. From the earlier scan:
  2513849  14095a855: imulq $0x1f20, 0x8(%rcx),%rsi
  2515732  14095c4e5: imulq $0x1f20, %r12, %r13
  2561040  140985c6b: imulq $0x1f20, %r8, %rax
  2564302  140988cb2: imulq $0x1f20, %rax, %rcx
  2585444  14099d61c: imulq $0x1f20, %rax, %rdx
  2588018  14099ff90: imulq $0x1f20, %rax, %rbp
  2588960  1409a0f43: imulq $0x1f20, %rdx, %r10
  2589209  1409a133e: imulq $0x1f20, %rax, %rcx
  2589466  1409a17b8: imulq $0x1f20, %rax, %rdi
  2595083  1409a6b43: imulq $0x1f20, %rax, %rcx
  2649174  1409d5941: imulq $0x1f20, %rax, %rbx     <- registrar
  2722815  140a17bf5: imulq $0x1f20, %r13, %r14     <- the bit-setter loop

The dispatcher is most likely one of the 0x14095xxxx-0x1409a6xxx ones. Let's
disassemble around each and look for a `call` through a loaded handler.
"""
import re
import subprocess
import sys

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

SITES = [0x14095A855, 0x14095C4E5, 0x140985C6B, 0x140988CB2,
         0x14099D61C, 0x14099FF90, 0x1409A0F43, 0x1409A133E,
         0x1409A17B8, 0x1409A6B43]


def dis(start, length=0xC0):
    r = subprocess.run([OBJ, "-d",
                        "--start-address=%d" % start,
                        "--stop-address=%d" % (start + length), EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append((int(m.group(1), 16), m.group(3).strip()))
    return out


def main():
    for s in SITES:
        print("=" * 74)
        print("site rva=%#x" % s)
        insns = dis(s - 0x30, 0x110)
        for addr, text in insns:
            mark = "  <===" if abs(addr - s) < 4 else ""
            print("  %#x  %s%s" % (addr - 0x140000000, text, mark))
        print()


if __name__ == "__main__":
    main()
