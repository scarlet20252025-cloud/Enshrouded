r"""Look at what the TameWildlifeEvent handler does with the payload, and why
the entity id is needed.

Recall the submit site inside func 0x47d5bc (the handler):
  0x47d73a  movq (%rsi), %rcx          ; rcx = [rsi]
  0x47d73d  leaq 0x118(%rbp), %rdx     ; rdx = &payload
  0x47d744  callq ResolveEnt           ; ResolveEnt(handle, &out)
  0x47d749  movq (%rsi), %rcx
  0x47d74c  callq GetCtx               ; rcx = [rsi], rax = GetCtx result
  0x47d751  movl 0x88(%rbx), %r8d      ; r8d = ??? (target entity id?)
  0x47d758  movq %rax, %rcx            ; rcx = ctx
  0x47d75b  movl 0x118(%rbp), %edx     ; edx = payload[0]
  0x47d761  callq 0x140954250          ; SendEventEx(ctx, payload[0], 0, ?)
  0x47d766  testb %al, %al
  0x47d768  je ...
  0x47d76a  movl %r12d, 0x88(%rbx)     ; zero something
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    r = subprocess.run([OBJ, "-d", "--start-address=0x14047D730",
                        "--stop-address=0x14047D7E0", EXE],
                       capture_output=True, text=True, errors="replace")
    print((r.stdout or "").strip()[-2200:])


if __name__ == "__main__":
    main()
