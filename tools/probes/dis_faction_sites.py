r"""The 48-byte Faction setter 0x14021C390 is only a BUILDER — it never uses
rcx (the ctx) at all. Its registers:

    0x21c390  testq %r8, %r8            ; r8 = const uint8_t* value
    0x21c393  je    ret
    0x21c395  pushq %rbx ; subq $0x20, %rsp
    0x21c39a  movzbl (%r8), %eax         ; eax = *value
    0x21c39e  movq %rdx, %rbx            ; rbx = rdx  (scratch buffer)
    0x21c3a1  movb %al, (%rdx)           ; *rdx = value
    0x21c3a3  callq 0x1402202c0          ; rcx = in/out, returns rax = new slot
    0x21c3a8  movl $0xA1F30F21, (%rax)   ; slot->hash = Faction
    0x21c3ae  movq %rbx, 0x8(%rax)       ; slot->ptr = &value
    0x21c3b2  movq $0x1, 0x10(%rax)      ; slot->size = 1
    0x21c3ba  ... pop ; ret

So the signature is:
    void SetFaction(void* collection /*rcx, in/out*/, void* scratch /*rdx*/,
                    const uint8_t* value /*r8*/)

and 0x1402202C0 is a growable 24-byte-slot-array appender:
    rcx = {  void** data;      // +0x00  (movq (%rbx),%rax in the slow path)
             u64     size;      // +0x08  count of slots
             u64     cap;       // +0x10  (movq 0x10(%rcx),%r9 in the reserve path)
             void*   growFn; }  // +0x18  virtual, called when size >= cap
    returns a pointer to slot[oldSize] (24 bytes each = leaq (rcx,rcx,2),rcx*8)

That is a COMPLETELY different channel from Enqueue, which is why our
WriteByteComponent(Faction) does nothing: we enqueue a 0x6D-byte component
record the engine never reads for Faction.

CRITICAL: the collection object lives in the caller. Disassemble the real call
sites to find out WHO owns it. Site 0x140222863 is inside a 8264-byte function,
which is probably the entity-spawn component pack — meaning the collection is a
per-entity component list, not a global.
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
    for site in (0x140222863, 0x14021C3AA):
        print("=" * 70)
        print("--- call site %#x ---" % site)
        for ln in dis(site - 0x60, site + 0x40):
            print(ln)
