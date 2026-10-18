"""Disassemble a range by RVA, printing VA alongside, with a hard cap.

Written because tools/peek.py `dis` takes a VA and the result was unusable when
given an RVA by mistake. Being explicit about which unit a number is in prevents
reading a disassembly of the wrong bytes and drawing conclusions from it.

Usage:
    python tools/rva_dis.py 0x97B790 0x60          # rva + length
    python tools/rva_dis.py --va 0x14097B790 0x60  # absolute VA instead
"""
import argparse
import os
import re
import shutil
import subprocess

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start")
    ap.add_argument("length")
    ap.add_argument("--va", action="store_true",
                    help="treat start as an absolute VA instead of an RVA")
    args = ap.parse_args()

    start = int(args.start, 0)
    length = int(args.length, 0)
    va = start if args.va else (IMAGE_BASE + start)
    rva = va - IMAGE_BASE

    print("rva 0x%X  va 0x%X  length 0x%X" % (rva, va, length))

    out = subprocess.run(
        [find_objdump(), "-d", "--start-address=%d" % va,
         "--stop-address=%d" % (va + length), EXE],
        capture_output=True, text=True, errors="replace")
    if out.returncode:
        print(out.stderr)
        return 1

    for line in (out.stdout or "").splitlines():
        m = re.match(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)$", line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        print("rva %08X  va %016X  %-24s %s"
              % (addr - IMAGE_BASE, addr, m.group(2).strip(), m.group(3)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
