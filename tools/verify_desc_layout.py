"""Verify the entity-factory descriptor layout by reading the real function.

Our SpawnAt() writes a descriptor as:
    +0x04  16-byte template GUID
    +0x18  pointer to a 24-byte-per-entry component array
    +0x20  u64 component count

and Create() at RVA 0x97B790 was confirmed to read desc+0x20 as a count capped
at 0x80. What was NOT verified is desc+0x18: if the component array pointer is
read from somewhere else, our two-component override (CurrentTransform +
OverrideLevel) is silently dropped and the wolf spawns wherever the template
says, which would make every positional conclusion drawn from a spawn wrong.

This prints every instruction in Create that references the descriptor, so the
question is settled from the binary rather than from a guess.

Usage: python tools/verify_desc_layout.py
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
CREATE_RVA = 0x97B790
LENGTH = 0x900


def find_objdump():
    clang = shutil.which("clang")
    if clang:
        cand = os.path.join(os.path.dirname(clang), "llvm-objdump.exe")
        if os.path.exists(cand):
            return cand
    return shutil.which("llvm-objdump") or "llvm-objdump"


def main():
    va = IMAGE_BASE + CREATE_RVA
    out = subprocess.run(
        [find_objdump(), "-d", "--start-address=%d" % va,
         "--stop-address=%d" % (va + LENGTH), EXE],
        capture_output=True, text=True, errors="replace")
    if out.returncode:
        print(out.stderr)
        return 1

    insns = []
    for line in (out.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$", line)
        if m:
            insns.append((int(m.group(1), 16) - IMAGE_BASE, m.group(2).strip(),
                          m.group(3).strip()))

    print("Create at RVA 0x%X: %d instructions" % (CREATE_RVA, len(insns)))
    print()

    # Anything that touches the descriptor pointer, which Create receives in
    # r8 and immediately copies into r12-adjacent slots.
    print("=== descriptor-referencing instructions ===")
    hits = 0
    for rva, raw, txt in insns:
        if re.search(r"%r8\b", txt) or "0x58(%rsp)" in txt:
            print("rva %08X  %-22s %s" % (rva, raw[:22], txt))
            hits += 1
    if not hits:
        print("(none in the first 0x%X bytes)" % LENGTH)

    print()
    print("=== the count field (desc+0x20) ===")
    for rva, raw, txt in insns:
        if "0x20(%r8)" in txt or "0x20(%rax)" in txt:
            print("rva %08X  %-22s %s" % (rva, raw[:22], txt))

    return 0


if __name__ == "__main__":
    sys.exit(main())
