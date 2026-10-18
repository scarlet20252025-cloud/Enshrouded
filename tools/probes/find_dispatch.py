r"""Decisive question: what does the ECS program dispatcher pass as `rcx` when it
calls a program handler?

The registrar 0x1409d5770 copies `descriptor->handler` (descriptor+0x10) into
`slot+0x28`. So a dispatcher must do something like:

    rax = slot->handler       ; movq 0x28(%rXX),%rax
    rcx = <something>
    callq *%rax               ; or callq *0x28(%rXX)

Find every indirect call through +0x28 and print the surrounding instructions so
we can see what rcx is set to immediately before the call.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

# indirect call through a register offset by 0x28
PAT = re.compile(r"callq?\s+\*0x28\(%r[a-z0-9]+\)")


def main():
    r = subprocess.run([OBJ, "-d", "--section=.text", EXE],
                       capture_output=True, text=True, errors="replace")
    lines = (r.stdout or "").splitlines()
    print("total lines:", len(lines))

    hits = []
    for i, ln in enumerate(lines):
        if PAT.search(ln):
            hits.append((i, ln.strip()))

    print("indirect calls via *0x28(reg):", len(hits))
    for i, ln in hits[:25]:
        print("=" * 70)
        for j in range(max(0, i - 14), min(len(lines), i + 3)):
            print(lines[j])


if __name__ == "__main__":
    main()
