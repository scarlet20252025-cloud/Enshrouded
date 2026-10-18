"""Decide whether the component-array pointer at desc+0x18 is read by Create().

Now that the full Create span is scanned (0x97B790..0x97D358, 1641
instructions), the evidence is: %r8 (the descriptor pointer) is used at +0x20
(count, capped 0x80) and +0x04 (GUID), and never at +0x18. But the component
array still has to come from somewhere -- a spawn with no components cannot
produce a wolf. The likely answer is that the array pointer is at a different
offset, and the 24-byte-per-entry walk at rva 0x97C455-0x97C6F5 is where to look:
those instructions read u16 tables at +0x84/+0xa84/+0x584, which is the entity
definition's slot layout, not our array.

So the remaining question is: what does Create() do with the descriptor after
reading the GUID, and where does it read the component list? This tool dumps the
region 0x97B8A9-0x97BB00 (where desc+4 becomes rdi and is passed to the
template loader at 0x14094c030) plus 0x97BC00-0x97BCE0 (the loop head), so the
answer can be read directly instead of inferred.

Usage: python tools/dump_create_regions.py
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


def dump(lo, hi, title):
    print("=== %s (rva 0x%X..0x%X) ===" % (title, lo, hi))
    for rva, raw, txt in disassemble(lo, hi - lo):
        print("  rva %08X  %-22s %s" % (rva, raw[:22], txt))
    print()


def main():
    # 1. The prologue of the real body: desc+4 -> rdi, then a call.
    dump(0x97B8A9, 0x97B920, "body entry: descriptor -> template loader")

    # 2. The loop head at 0x97BC90, which reloads 0x58(%rsp) (the &desc[0x20]
    #    saved earlier) and compares against a count.
    dump(0x97BC90, 0x97BD00, "loop head")

    # 3. The component-walk region that reads the definition's slot tables.
    dump(0x97C440, 0x97C560, "slot-table reads")

    return 0


if __name__ == "__main__":
    sys.exit(main())
