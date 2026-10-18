"""Answer where Create() actually reads the component array.

The evidence gathered so far:
  - Create() receives the descriptor in r8 and reads desc+0x20 (count, capped
    at 0x80) and desc+0x04 (GUID, via movups 0x4(%r8)).
  - Across the full span (0x97B790..0x97D358, 1641 instructions) %r8 is never
    used at +0x18.
  - desc+4 becomes rdi and is handed to the template loader 0x14094c030, which
    seeds a struct with the constant 0x39768775 -- the TemplateResource type id
    seen in the KFC data. So desc+4 is a template *reference* key, and the
    template itself is looked up from the world.

Conclusion to verify: the component list is not passed by us at all. It is read
from the resolved template, which is why the community mod passes only
CurrentTransform + OverrideLevel and still gets a working enemy -- those two are
merged with (or override) the template's own components, and the GUID alone
selects the wolf.

If that is right, the correct minimal descriptor is:
    +0x04  16-byte template GUID
    +0x20  u64 count of our override components
    +0x28  pointer to our 24-byte-per-entry override array   (NOT +0x18)
and the +0x18 field we write is either unused or means something else.

This tool prints the instructions between the count check (0x97B7C7) and the
template-loader call (0x97B8EA) plus the loop at 0x97BCC0 that walks the
component entries, so the offset can be read off directly.

Usage: python tools/find_component_array_offset.py
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
    # The component-walk loop: 0x97BCC0 reads 0x18(%rdx) where rdx came from
    # 0xe10(%rbp), i.e. an internal object, not our descriptor. Print the loop
    # body with enough context to see where its data pointer originates.
    print("=== component-walk loop (rva 0x97BCC0 .. 0x97BD80) ===")
    for rva, raw, txt in disassemble(0x97BCC0, 0xC0):
        print("  rva %08X  %-22s %s" % (rva, raw[:22], txt))

    print()
    print("=== where 0xe10(%rbp) is written (the array base) ===")
    for rva, raw, txt in disassemble(0x97B790, 0xBC8):
        if "0xe10(%rbp)" in txt or "0xe08(%rbp)" in txt:
            print("  rva %08X  %-22s %s" % (rva, raw[:22], txt))

    return 0


if __name__ == "__main__":
    sys.exit(main())
