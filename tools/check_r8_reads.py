"""Decisive check: does Create() ever read the descriptor's +0x18 field?

The whole "spawn at a position" feature rests on this one question. Our code
(and M182's) writes the component array pointer at desc+0x18 and the count at
desc+0x20. A region dump suggested +0x18 is never read, but that would make
M182's own calibration path dead code, so the claim needs to be proven rather
than assumed from one disassembly window.

This tool disassembles the ENTIRE function span (all .pdata entries that cover
it) and prints every instruction that mentions %r8, so the answer is read off
directly instead of inferred from a partial view.

Usage: python tools/check_r8_reads.py
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
SPAN_START = 0x97B790
SPAN_END = 0x97D358


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
    ins = disassemble(SPAN_START, SPAN_END - SPAN_START)
    print("disassembled %d instructions over rva 0x%X..0x%X" % (len(ins), SPAN_START, SPAN_END))
    print()

    print("=== every instruction mentioning r8 ===")
    hits = 0
    for rva, raw, txt in ins:
        # Match %r8 as a whole register, not r8d/r8w substrings.
        if re.search(r"(?<![A-Za-z0-9])%r8(?![A-Za-z0-9])", txt):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))
            hits += 1
    print("  -> %d instructions use %%r8" % hits)

    print()
    print("=== every read of [r8+disp] ===")
    for rva, raw, txt in ins:
        if re.search(r"0x[0-9a-f]+\(%r8\)", txt):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))

    print()
    print("=== every read of [r8] (no displacement) ===")
    for rva, raw, txt in ins:
        if re.search(r"\(%r8\)", txt) and not re.search(r"0x[0-9a-f]+\(%r8\)", txt):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))

    print()
    print("=== where %r8 is loaded (movq into r8) ===")
    for rva, raw, txt in ins:
        if re.search(r",\s*%r8$", txt) and txt.startswith("mov"):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
