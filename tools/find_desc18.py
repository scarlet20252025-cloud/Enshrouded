"""Find every read of the descriptor's component-array pointer.

Now that .pdata is known to split Create into three consecutive entries
(0x97B790-0x97B8BC, 0x97B8BC-0x97B9EB, 0x97B9EB-0x97D358), scan the whole span
rather than the first fragment, and answer the actual question:

    does Create() read desc+0x18 at all?

SpawnAt() writes the 24-byte-per-entry component array pointer at desc+0x18.
The count at desc+0x20 is confirmed to be read and capped at 0x80. If +0x18 is
never read, the array we build is dropped, and the spawn would use whatever the
template itself says -- which would make every positional conclusion from a
spawn invalid.

Usage: python tools/find_desc18.py
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
SPAN_LO = 0x97B790
SPAN_HI = 0x97D358


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
    insns = disassemble(SPAN_LO, SPAN_HI - SPAN_LO)
    print("Create span 0x%X..0x%X: %d instructions"
          % (SPAN_LO, SPAN_HI, len(insns)))
    print()

    # Track the descriptor pointer: it arrives in r8, is spilled to 0x18(%rsp).
    print("=== r8 / 0x18(%rsp) (the descriptor pointer) ===")
    for rva, raw, txt in insns:
        if re.search(r"%r8\b", txt) or "0x18(%rsp)" in txt:
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))

    print()
    print("=== 24-byte stride arithmetic (component array walk) ===")
    for rva, raw, txt in insns:
        if "$0x18" in txt and ("add" in txt or "lea" in txt or "shl" in txt):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))

    print()
    print("=== reads at +0x18/+0x1c of a pointer register ===")
    for rva, raw, txt in insns:
        if re.search(r"0x1[0-9a-f]\(%r", txt):
            print("  rva %08X  %-24s %s" % (rva, raw[:24], txt))

    return 0


if __name__ == "__main__":
    sys.exit(main())
