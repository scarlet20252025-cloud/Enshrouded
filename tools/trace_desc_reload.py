"""Resolve where the desc pointer lives after the prologue spills it.

At the entry the descriptor (arg3, win64 %r8) is spilled to 0x18(%rsp). After
the pushes and the 0xed8-byte frame, that slot has moved. The two reads that
matter are:

    rva 0x97B7BB   leaq 0x20(%r8), %rax     <- still %r8 here (pre-push, so it
                                              is the ORIGINAL arg3)
    rva 0x97B8A9   movups 0x4(%r8), %xmm0   <- after the frame is built

If the 0x97B8A9 read is arg3 too, then desc+0x04 is genuinely the GUID and the
descriptor really is arg3 throughout. What we still need is the reload address
of 0x18(%rsp) after the frame shift, and to see whether anything reads it.

Frame shift: rsp_at_entry = R. Spills go to R+0x08..0x20. Then 4 pushes
(-0x20), then rbp = rsp-0xdd8, then rsp -= 0xed8.

    rsp_after = R - 0x20 - 0xed8
    spill at R+0x18  ==  rsp_after + 0x20 + 0xed8 + 0x18 = rsp_after + 0xF10

So the reload is 0xF10(%rsp) (or an rbp-relative form: rbp = rsp_after+0xdd8,
so the spill is rbp + 0xF10 - 0xdd8 = rbp + 0x138).

Print every instruction that references rsp+0xF10 or rbp+0x138 to find where
the descriptor is re-read.

Usage: python tools/trace_desc_reload.py
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
    print("disassembled %d instructions" % len(ins))
    print()
    print("=== computed reload slots: rsp+0xF10, rbp+0x138 ===")
    found = 0
    for rva, raw, txt in ins:
        if re.search(r"0xf10\(%rsp\)", txt) or re.search(r"0x138\(%rbp\)", txt):
            print("  rva %08X  %-26s %s" % (rva, raw[:26], txt))
            found += 1
    if not found:
        print("  (none — the spill is never reloaded, so arg3 is only read via"
              " the live %r8 at 0x97B7BB / 0x97B8A9)")
    print()

    print("=== every instruction reading the stack slot holding desc (0x18(%rsp) family) ===")
    for rva, raw, txt in ins:
        if re.search(r"0x1[0-9a-f]0\(%rsp\)", txt):
            print("  rva %08X  %-26s %s" % (rva, raw[:26], txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
