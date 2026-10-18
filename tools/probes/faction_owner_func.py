r"""Faction is written by a per-entity COMPONENT LIST on the stack, not the
component queue. Two independent confirmations from the two call sites above:

Site 0x222861 (inlined into an 8264-byte spawn-pack builder):
        leaq 0x16618(%rbp), %rcx        ; &copy of the faction byte, ON THE STACK
        movl $0xA1F30F21, (%rax)        ; slot.hash
        movq %rcx, 0x8(%rax)            ; slot.ptr = &stackbyte
        movq $0x1, 0x10(%rax)           ; slot.size = 1
    ... where `rax` comes from the inlined 0x1402202C0 slow path reading
        rbp+0xf0 = data, rbp+0xf8 = count, rbp+0x100 = cap, rbp+0x108 = growFn

Site 0x21c3a1 (the 48-byte helper):
        movb %al, (%rdx)                ; scratch buffer, caller-supplied
        movl $hash, (%rax) ; movq %rbx, 0x8(%rax) ; movq $1, 0x10(%rax)

So both write into a caller-owned array of {u32 hash; void* ptr; u64 size}
triples. That array is the descriptor passed to the entity spawner. This is
NOT reachable from the Enqueue queue we hook.

What this means for the mod:
  * Our `WriteByteComponent` is ENQUEUE-shaped, so it can never set Faction.
  * The correct route is: build the same 24-byte descriptor array and feed it
    to whatever function consumes it. Find that consumer next.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def dis(start, stop):
    r = subprocess.run([OBJ, "-d", "--start-address=%#x" % start,
                        "--stop-address=%#x" % stop, EXE],
                       capture_output=True, text=True, errors="replace")
    out = []
    for ln in (r.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
        if m:
            out.append("%#-9x %s" % (int(m.group(1), 16) - 0x140000000,
                                    m.group(3).strip()))
    return out


if __name__ == "__main__":
    # What function is 0x222861 inside? Print its .pdata bounds and the head.
    for ln in dis(0x140221280, 0x140221400):
        print(ln)
