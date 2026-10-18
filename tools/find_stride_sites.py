"""Find the ECS program dispatcher by searching for the slot stride.

Why this and not the previous attempts:

  * `callq *0x28(%reg)` found 123 sites in 107 functions. Too many, and none
    also referenced the program table, so the table base must be reached
    indirectly (a pointer stored somewhere), which a constant search misses.

  * `imul $0x1f20` is the real fingerprint. The registrar (0x1409d5770) stores
    each program into a slot array at `world+0x746360` with **stride 0x1f20**.
    Any code that walks that array has to multiply an index by 0x1f20, and
    0x1f20 is far too specific a constant to appear by accident.

This tool scans the whole .text for every instruction whose immediate operand
is 0x1f20 (in any encoding: imul, add, sub, lea displacement, cmp) and reports
each site plus the .pdata function that contains it and that function's size.
Sites inside the registrar itself are marked so they can be ignored.

Usage: python tools/find_stride_sites.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

STRIDE = 0x1F20
REGISTRAR_RVA = 0x9D5770

# (label, regex) — every way 0x1f20 can show up as an immediate.
PATTERNS = [
    # imul r32, r/m32, imm32   (69 /r id)
    ("imul imm32", re.compile(rb"\x69[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    # imul r32, r/m32, imm8    (6b /r ib) — imm8 cannot hold 0x1f20, so this
    # pattern can never match and is listed only to say so explicitly.
    ("add imm32", re.compile(rb"\x81[\xc0-\xff]" + struct.pack("<i", STRIDE))),
    ("sub imm32", re.compile(rb"\x81[\xe8-\xff]" + struct.pack("<i", STRIDE))),
    # cmp r/m32, imm32  (81 /7)
    ("cmp imm32", re.compile(rb"\x81[\xf8-\xff]" + struct.pack("<i", STRIDE))),
    # lea r32, [r + disp32]
    ("lea disp32", re.compile(rb"\x8d[\x80-\xff]" + struct.pack("<i", STRIDE))),
    # lea r64, [r + disp32]  (48 8d /r with mod=10)
    ("lea disp32", re.compile(rb"\x48\x8d[\x80-\xbf]" + struct.pack("<i", STRIDE))),
]


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()

    secs, base = pe_common.sections(exe)
    print("%s  (%d bytes, image base 0x%X)" % (exe, len(data), base))
    for name, va, raw, rsize, vsize in secs:
        print("  %-8s va=0x%08X raw=0x%08X rsize=0x%08X vsize=0x%08X"
              % (name, va, raw, rsize, vsize))

    text = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            text = (va, raw, rsize)
            break
    if text is None:
        raise SystemExit(".text not found")
    tva, traw, tsize = text
    print("\n.text va=0x%X raw=0x%X size=0x%X" % (tva, traw, tsize))

    funcs = pe_common.runtime_functions(data)
    print(".pdata runtime functions: %d" % len(funcs))

    seen = {}
    for label, pat in PATTERNS:
        for m in pat.finditer(data, traw, traw + tsize):
            rva = m.start() - traw
            if rva not in seen:
                seen[rva] = label

    if not seen:
        print("\nno 0x%X immediate found in .text" % STRIDE)
        return 1

    print("\n%d distinct site(s) with immediate 0x%X:" % (len(seen), STRIDE))
    for rva in sorted(seen):
        f = pe_common.func_of(funcs, rva)
        va = common.IMAGE_BASE + rva
        if f:
            fb, fe = f
            size = fe - fb
            tag = ""
            if fb == REGISTRAR_RVA:
                tag = "  <== REGISTRAR (expected, ignore)"
            elif size >= 4000:
                tag = "  <== LARGE (%d B) - dispatcher candidate" % size
            print("  rva 0x%08X  va 0x%012X  %-10s func 0x%08X (%5d B)%s"
                  % (rva, va, seen[rva], fb, size, tag))
        else:
            print("  rva 0x%08X  va 0x%012X  %-10s (no .pdata bounds)"
                  % (rva, va, seen[rva]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
