r"""Find where 0x1409bab60's result buffer is written and what its element
stride is, by looking at the CALLER (wildlife_enemy_transformer at 0x480c70):

  140480c84: movl $0xa8, %r8d            ; 3rd arg = 0xa8
  140480c8a: leaq 0x30(%rsp), %rdx       ; 2nd arg = &stack[0x30]
  140480c8f: movq %rcx, %r14
  140480c92: callq 0x1409bab60

So the call is f(world, &out, 0xa8). The out buffer is 0xa8 bytes.
Then 0x1409b5a50 is called with the SAME (rcx, rdx) pair — it consumes what
0x1409bab60 produced. Print the first 0xa8 bytes' interpretation by reading the
game's own usage in 0x480c70 (offsets -0x30..-0x68 relative to rbp where
rsp was 0x30 lower).

Decode which fields of the 0xa8 struct 0x480c70 reads.
"""
import re
import subprocess

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJDUMP, "-d", "--section=.text",
                        "--start-address=%d" % 0x140480C70,
                        "--stop-address=%d" % 0x140481056, EXE],
                       capture_output=True, text=True, errors="replace")
    text = r.stdout or ""
    for ln in text.splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if not m:
            continue
        insn = m.group(3).strip()
        if re.search(r"\(%rbp\)|\(%rsp\)", insn) and re.search(r"-0x[0-9a-f]+\(%rbp\)", insn):
            print("%s  %s" % (m.group(1), insn))


if __name__ == "__main__":
    main()
