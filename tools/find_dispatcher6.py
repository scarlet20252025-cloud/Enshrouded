"""Re-do the dispatcher search with the correct call-[reg+0x28] pattern.

The previous run used an opcode list that was wrong: `FF /2` (call r/m) with a
disp8 of 0x28 covers the modrm bytes 0x50..0x77, not just the 13 encodings
that were listed. With the full range there are 172 sites, not 3 — so the
earlier "no function has both" conclusion was an artefact of a broken pattern,
not a fact about the binary.

This tool redoes the intersection properly and also reports, for each
candidate, whether the function loads the slot base 0x746350 through a pointer
chain (mov reg,[reg+0x746350] / lea reg,[reg+0x746350]) rather than only via
the raw 4-byte constant.

Usage: python tools/find_dispatcher6.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

STRIDE = 0x1F20
TABLE_BASES = [0x746360, 0x746350]

# call qword ptr [reg + 0x28]:  FF /2 with mod=01, disp8=0x28.
# modrm 0x50..0x57 (reg=rax..rdi, rm=base) and 0x58..0x5f would be [reg+rax*1]
# which is not what we want; 0x60..0x77 are [reg+disp8] for the other bases.
CALL28 = re.compile(rb"\xff[\x60-\x77]\x28")
# REX.B variant for r8..r15
CALL28_REX = re.compile(rb"\x41\xff[\x60-\x77]\x28")

STRIDE_PATTERNS = [
    ("imul r64,imm32", re.compile(rb"\x48\x69[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("imul r64,imm32", re.compile(rb"\x4d\x69[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("imul r32,imm32", re.compile(rb"\x69[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("add r64,imm32",  re.compile(rb"\x48\x81[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("add r64,imm32",  re.compile(rb"\x49\x81[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("add r32,imm32",  re.compile(rb"\x81[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("sub r32,imm32",  re.compile(rb"\x81[\xe8-\xff]" + struct.pack("<i", STRIDE))),
]

BASE_PATTERNS = []
for off in TABLE_BASES:
    n = struct.pack("<i", off)
    BASE_PATTERNS += [
        ("lea r64,[r+base]", re.compile(rb"\x48\x8d[\x80-\xbf]" + n)),
        ("lea r32,[r+base]", re.compile(rb"\x8d[\x80-\xbf]" + n)),
        ("mov r64,[r+base]", re.compile(rb"\x48\x8b[\x80-\xbf]" + n)),
        ("mov r32,[r+base]", re.compile(rb"\x8b[\x80-\xbf]" + n)),
        ("add r64,base",     re.compile(rb"\x48\x81[\xc0-\xff]" + n)),
    ]


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = tsize = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw, tsize = raw, rsize
            break
    text = data[traw:traw + tsize]
    funcs = pe_common.runtime_functions(data)
    print(".text raw=0x%X size=0x%X, %d runtime functions"
          % (traw, tsize, len(funcs)))

    call28 = {}
    for pat in (CALL28, CALL28_REX):
        for m in pat.finditer(text):
            f = pe_common.func_of(funcs, m.start())
            if f:
                call28.setdefault(f[0], []).append(m.start())
    total = sum(len(v) for v in call28.values())
    print("call [reg+0x28]: %d sites in %d functions" % (total, len(call28)))

    stride = {}
    for label, pat in STRIDE_PATTERNS:
        for m in pat.finditer(text):
            f = pe_common.func_of(funcs, m.start())
            if f:
                stride.setdefault(f[0], []).append((m.start(), label))
    base_ref = {}
    for label, pat in BASE_PATTERNS:
        for m in pat.finditer(text):
            f = pe_common.func_of(funcs, m.start())
            if f:
                base_ref.setdefault(f[0], []).append((m.start(), label))

    print("functions using stride 0x%X: %d" % (STRIDE, len(stride)))
    print("functions referencing the slot base: %d" % len(base_ref))

    both = set(call28) & (set(stride) | set(base_ref))
    print("\n=== BOTH call[+0x28] and a table constant: %d ===" % len(both))

    def size_of(fb):
        for b, e in funcs:
            if b == fb:
                return e - b
        return None

    for fb in sorted(both):
        tags = []
        if fb in stride:
            tags.append("stride x%d" % len(stride[fb]))
        if fb in base_ref:
            tags.append("base x%d" % len(base_ref[fb]))
        print("  func 0x%08X (%s B)  call28 x%d  [%s]"
              % (fb, size_of(fb), len(call28[fb]), ", ".join(tags)))
        for rva, label in base_ref.get(fb, [])[:4]:
            print("      %s @ 0x%08X" % (label, rva))
        for rva, label in stride.get(fb, [])[:4]:
            print("      %s @ 0x%08X" % (label, rva))

    print("\n=== all functions referencing the slot base (any size) ===")
    for fb in sorted(base_ref):
        print("  func 0x%08X (%s B)  call28 x%d  base-sites %s"
              % (fb, size_of(fb), len(call28.get(fb, [])),
                 ",".join("0x%X" % r for r, _ in base_ref[fb][:6])))

    print("\n=== largest call[+0x28] functions (top 15) ===")
    ranked = sorted(call28.items(), key=lambda kv: -(size_of(kv[0]) or 0))[:15]
    for fb, sites in ranked:
        tag = ""
        if fb in stride:
            tag += " +stride"
        if fb in base_ref:
            tag += " +base"
        print("  func 0x%08X (%5s B)  call28 x%d%s"
              % (fb, size_of(fb), len(sites), tag))
    return 0


if __name__ == "__main__":
    sys.exit(main())
