"""Trace where 0xe10(%rbp) is initialised as a pointer.

At rva 0x97BCC0 the component-walk loop does:

    movq 0x18(%rdx), %r13      ; rdx = [rbp+0xe10]  (an object, not our desc)
    addq %rsi, %r13            ; rsi advances by 0x18 each iteration
    ...
    addq $0x18, %rsi

so it walks an internal array of 24-byte entries, one per component, whose base
is [rbp+0xe10]. That object is created inside Create(), not passed by us.

But 0xe10(%rbp) is first written at 0x97B80C as a single byte (movb %al), and
only later read as a full pointer at 0x97BB9F / 0x97BC95. Something between
those writes turns that byte slot into a pointer slot, which means rbp-relative
0xe10 is a *union* or a struct whose first byte is a flag and whose body is a
pointer. That is exactly the shape of a small inline struct built on the stack.

Decide it by reading the region 0x97BB60..0x97BC90, where 0xe10(%rbp) is loaded
as a pointer and the loop is entered.

Usage: python tools/trace_e10.py
"""
import os
import re
import shutil
import subprocess
import sys

import common
EXE = common.exe_path()
if not EXE:
    raise SystemExit(
        'enshrouded.exe not found; set WOLFMOUNT_EXE or ENSHROUDED_EXE'
        ' to the full path')
IMAGE_BASE = 0x140000000


def find_objdump():
    clang = shutil.which("clang")
    if clang:
        cand = os.path.join(os.path.dirname(clang), "llvm-objdump.exe")
        if os.path.exists(cand):
            return cand
    return shutil.which("llvm-objdump") or "llvm-objdump"


def disassemble(rva, length):
    va = IMAGE_BASE + rva
    out = subprocess.run(
        [find_objdump(), "-d", "--start-address=%d" % va,
         "--stop-address=%d" % (va + length), EXE],
        capture_output=True, text=True, errors="replace")
    if out.returncode:
        return []
    res = []
    for line in (out.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$", line)
        if m:
            res.append((int(m.group(1), 16) - IMAGE_BASE, m.group(2).strip(),
                        m.group(3).strip()))
    return res


def main():
    print("=== rva 0x97BB60 .. 0x97BC90 (loop entry, 0xe10 becomes a pointer) ===")
    for rva, raw, txt in disassemble(0x97BB60, 0x130):
        print("  rva %08X  %-22s %s" % (rva, raw[:22], txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
