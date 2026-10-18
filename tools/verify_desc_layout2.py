"""Decide whether Create's component-array pointer comes from desc+0x18.

Context: SpawnAt() builds a descriptor with the component array pointer at
+0x18 and a count at +0x20. The count read at +0x20 is confirmed (capped at
0x80), but the pointer at +0x18 was never verified -- Create only references
%r8 at +0x20 and +0x04, so +0x18 is never touched in the first 0x900 bytes.
If the real pointer lives elsewhere, our CurrentTransform/OverrideLevel
override is dropped silently and the wolf spawns at the template's own
position, which would invalidate every positional result from a spawn.

Method: enumerate every place Create stores or reloads the descriptor pointer
(%r8 and its spill slot 0x58(%rsp)), then disassemble each of those sites with
enough context to see which offset is dereferenced. Purely static, read-only.

Usage: python tools/verify_desc_layout2.py
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
            res.append((int(m.group(1), 16) - IMAGE_BASE, m.group(3).strip()))
    return res


def main():
    va = IMAGE_BASE + CREATE_RVA
    out = subprocess.run(
        [find_objdump(), "-d", "--start-address=%d" % va,
         "--stop-address=%d" % (va + LENGTH), EXE],
        capture_output=True, text=True, errors="replace")
    insns = []
    for line in (out.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$", line)
        if m:
            insns.append((int(m.group(1), 16) - IMAGE_BASE, m.group(3).strip()))

    # Sites where the descriptor pointer is spilled to or reloaded from the
    # stack. Those are the only ways it can reach a later dereference.
    spill = [(r, t) for r, t in insns
             if re.search(r"0x18\(%rsp\)", t) or re.search(r"0x58\(%rsp\)", t)]

    print("=== spill/reload sites of the descriptor pointer (%d) ===" % len(spill))
    for r, t in spill:
        print("  rva %08X  %s" % (r, t))

    print()
    print("=== each site, with 10 instructions of context ===")
    for r, t in spill:
        print("--- around rva %08X ---" % r)
        ctx = disassemble(max(CREATE_RVA, r - 0x20), 0x50)
        for cr, ct in ctx:
            mark = ">>" if cr == r else "  "
            print("%s rva %08X  %s" % (mark, cr, ct))
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
