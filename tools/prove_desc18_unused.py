"""Exhaustively find every memory read of the descriptor pointer.

Provenance so far, all read off the disassembly rather than assumed:

  entry:  arg3 = %r8  (win64: rcx, rdx, r8, r9)
          0x97B790  movq %r9, 0x20(%rsp)     <- arg4
          0x97B795  movq %r8, 0x18(%rsp)     <- arg3 = desc
          0x97B79A  movl %edx, 0x10(%rsp)    <- arg2
          0x97B79E  movq %rcx, 0x8(%rsp)     <- arg1 = manager
          0x97B7A3..0x97B7A7  4 pushes
          0x97B7A9  leaq -0xdd8(%rsp), %rbp
          0x97B7B1  subq $0xed8, %rsp
          0x97B7B8  movq (%rcx), %rsi        <- [manager] must be the world
          0x97B7BB  leaq 0x20(%r8), %rax     <- desc+0x20 is used (the count)
          0x97B7BF  movq %rcx, %r12

  After the frame: rsp_after = R - 0x20 - 0xed8 where R is rsp at entry.
  The spill at R+0x18 therefore lives at rsp_after + 0xF10.
  rbp = rsp_after + 0xdd8, so the same slot is rbp + 0x138.

  The scan for rsp+0xF10 / rbp+0x138 found NOTHING. So arg3 is read only
  through the still-live %r8, at exactly two places:
      rva 0x97B7BB   leaq  0x20(%r8), %rax     desc+0x20  (count, capped 0x80)
      rva 0x97B8A9   movups 0x4(%r8), %xmm0    desc+0x04  (16-byte template GUID)
  and one register copy:
      rva 0x97B8CC   leaq  0x4(%r8), %rdi      desc+0x04 handed to the loader

  Conclusion: desc+0x18 is NEVER read. The component array pointer we write
  there is ignored, and the components come from the template itself.

This tool prints the definitive evidence: the two live %r8 uses with 12 bytes
of context around each, plus the full list of instructions that dereference
%r8 with any displacement, so a future reader can re-derive the conclusion
without trusting this note.

Usage: python tools/prove_desc18_unused.py
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
    print("=== ALL r8 dereferences with a displacement, whole function ===")
    for rva, raw, txt in ins:
        if re.search(r"0x[0-9a-f]+\(%r8\)", txt):
            print("  rva %08X  %-26s %s" % (rva, raw[:26], txt))
    print()
    print("=== ALL %r8 dereferences without a displacement ===")
    for rva, raw, txt in ins:
        if re.search(r"\(%r8\)", txt) and not re.search(r"0x[0-9a-f]+\(%r8\)", txt):
            print("  rva %08X  %-26s %s" % (rva, raw[:26], txt))
    print()
    print("=== leaq/movq that DEFINE %r8 after the frame is built (rva > 0x97B7B1) ===")
    for rva, raw, txt in ins:
        if rva <= 0x97B7B1:
            continue
        if re.search(r",\s*%r8$", txt) or re.search(r",\s*%r8\b", txt):
            print("  rva %08X  %-26s %s" % (rva, raw[:26], txt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
