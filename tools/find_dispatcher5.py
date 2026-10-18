"""Cross-reference `call qword ptr [reg+0x28]` against the slot-table walkers.

Known so far:

  * registrar inner store (0x9D48B0) proved the slot layout:
        imul rbx, rax, 0x1f20 ; add rbx, 0x746350 ; add rbx, rsi
        mov  [rbx],      r15                 ; slot+0x00 = descriptor ptr
        movups [rbx+0x10], xmm0              ; slot+0x10 = descriptor+0x00
        mov  rax, [r15+0x10] ; mov [rbx+0x28], rax   ; slot+0x28 = HANDLER
        mov  ecx, [r15+0x180]; mov [rbx+0x20], ecx   ; slot+0x20 = flags
        mov  eax, [r15+0x184]; mov [rbx+0x24], eax   ; slot+0x24
    so slot+0x28 really is the handler pointer the registrar stores.

  * 123 sites in .text are `call [reg+0x28]`. That alone is useless, because
    +0x28 is a common vtable slot.

  * 10 functions reference the slot table (base 0x746350/0x746360 or the
    related 0x745A48/0x745A58/0x743B10). NONE of them is large, so the
    dispatcher probably reaches the table through a pointer it loaded earlier
    rather than through a displacement.

The decisive test: a real dispatcher must (a) call [reg+0x28] AND (b) advance a
pointer by 0x1f20 or index by 0x1f20 somewhere in the same function. This tool
intersects those two sets.

Usage: python tools/find_dispatcher5.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

# call qword ptr [reg + 0x28], every register form.
CALL28 = [
    (b"\xff\x51\x28", "rcx"),
    (b"\xff\x52\x28", "rdx"),
    (b"\xff\x53\x28", "rbx"),
    (b"\xff\x55\x28", "rbp"),
    (b"\xff\x56\x28", "rsi"),
    (b"\xff\x57\x28", "rdi"),
    (b"\x41\xff\x50\x28", "r8"),
    (b"\x41\xff\x51\x28", "r9"),
    (b"\x41\xff\x52\x28", "r10"),
    (b"\x41\xff\x53\x28", "r11"),
    (b"\x41\xff\x55\x28", "r13"),
    (b"\x41\xff\x56\x28", "r14"),
    (b"\x41\xff\x57\x28", "r15"),
]

STRIDE = 0x1F20
STRIDE_PATTERNS = [
    re.compile(rb"\x69[\xc0-\xff]" + struct.pack("<i", STRIDE)),      # imul imm32
    re.compile(rb"\x81[\xc0-\xff]" + struct.pack("<i", STRIDE)),      # add imm32
    re.compile(rb"\x81[\xe8-\xff]" + struct.pack("<i", STRIDE)),      # sub imm32
    re.compile(rb"\x48\x81[\xc0-\xff]" + struct.pack("<i", STRIDE)),  # add r64, imm32
    re.compile(rb"\x49\x81[\xc0-\xff]" + struct.pack("<i", STRIDE)),  # add r8-15, imm32
    re.compile(rb"\x48\x69[\xc0-\xff]" + struct.pack("<i", STRIDE)),  # imul r64 imm32
    re.compile(rb"\x4d\x69[\xc0-\xff]" + struct.pack("<i", STRIDE)),  # imul r8-15 imm32
]

# Slot-table base offsets found by find_slot_table_refs.py.
TABLE_BASES = [0x746360, 0x746350, 0x745A48, 0x745A58, 0x743B10]


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw, tsize = raw, rsize
            break
    if traw is None:
        raise SystemExit(".text not found")
    funcs = pe_common.runtime_functions(data)
    print(".text raw=0x%X size=0x%X, %d runtime functions" % (traw, tsize, len(funcs)))

    # --- collect call [reg+0x28] sites, grouped by function ------------------
    call28_funcs = {}
    for pat, reg in CALL28:
        for m in re.finditer(re.escape(pat), data[traw:traw + tsize]):
            rva = m.start()
            f = pe_common.func_of(funcs, rva)
            if not f:
                continue
            call28_funcs.setdefault(f[0], []).append((rva, reg))
    print("call [reg+0x28] sites inside functions: %d, in %d functions"
          % (sum(len(v) for v in call28_funcs.values()), len(call28_funcs)))

    # --- functions that also use the stride or a table base -----------------
    stride_funcs = {}
    for pat in STRIDE_PATTERNS:
        for m in pat.finditer(data[traw:traw + tsize]):
            rva = m.start()
            f = pe_common.func_of(funcs, rva)
            if f:
                stride_funcs.setdefault(f[0], []).append(rva)
    base_funcs = {}
    for off in TABLE_BASES:
        needle = struct.pack("<I", off)
        for m in re.finditer(re.escape(needle), data[traw:traw + tsize]):
            rva = m.start()
            f = pe_common.func_of(funcs, rva)
            if f:
                base_funcs.setdefault(f[0], []).append(rva)
    print("functions using stride 0x%X: %d" % (STRIDE, len(stride_funcs)))
    print("functions using a table base: %d" % len(base_funcs))

    both = set(call28_funcs) & (set(stride_funcs) | set(base_funcs))
    print("\n=== functions with BOTH call[+0x28] and a table constant: %d ==="
          % len(both))
    if not both:
        print("(none - the dispatcher reaches the table through a pointer)")

    def size_of(fb):
        for b, e in funcs:
            if b == fb:
                return e - b
        return None

    for fb in sorted(both):
        why = []
        if fb in stride_funcs:
            why.append("stride x%d" % len(stride_funcs[fb]))
        if fb in base_funcs:
            why.append("table-base x%d" % len(base_funcs[fb]))
        print("  func 0x%08X (%s B)  call28 x%d  [%s]"
              % (fb, size_of(fb), len(call28_funcs[fb]), ", ".join(why)))
        for rva, reg in call28_funcs[fb][:6]:
            print("      call [%s+0x28] @ 0x%08X" % (reg, rva))

    # --- the other direction: biggest functions that call [+0x28] -----------
    print("\n=== largest functions that call [reg+0x28] (top 12) ===")
    ranked = sorted(call28_funcs.items(),
                    key=lambda kv: -(size_of(kv[0]) or 0))[:12]
    for fb, sites in ranked:
        tag = ""
        if fb in stride_funcs:
            tag += " +stride"
        if fb in base_funcs:
            tag += " +table-base"
        print("  func 0x%08X (%5s B)  call28 x%d%s"
              % (fb, size_of(fb), len(sites), tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
