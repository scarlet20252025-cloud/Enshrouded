"""Decode the program-slot walk in func 0xA16910 and 0x9D46E0.

Both functions contain the slot-table base constant 0x746360/0x746350 and the
stride 0x1f20, so they walk the ECS program table. The question this answers is
WHICH of them calls the handler (slot+0x28) and under what condition, because
that is the dispatcher we need to hook.

Rather than a full disassembler, this prints a small instruction-window view:
the raw bytes of each region of interest plus a decode of the specific forms
that matter (lea with disp32, imul/add with the stride, indirect call).

Usage: python tools/decode_slot_walk.py [--func RVA]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

REGIONS = {
    0x9D46E0: (0x9D47A0, 0x9D4820),
    0xA16910: (0xA16A20, 0xA16B00),
    0x9D48B0: (0x9D48B0, 0x9D4980),
}


def hexdump(data, start, end, label):
    print("\n=== %s  (0x%08X..0x%08X) ===" % (label, start, end))
    for k in range(start, end, 16):
        row = data[k:k + 16]
        if not row:
            break
        hexs = " ".join("%02X" % b for b in row)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        print("  0x%08X  %-47s  %s" % (k, hexs, asc))


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw = raw
            break

    args = sys.argv[1:]
    if "--func" in args:
        i = args.index("--func")
        target = int(args[i + 1], 0)
        length = int(args[i + 2], 0) if i + 2 < len(args) else 0x200
        funcs = pe_common.runtime_functions(data)
        f = pe_common.func_of(funcs, target)
        if not f:
            raise SystemExit("0x%X is not inside a .pdata function" % target)
        b, e = f
        end = min(b + length, e)
        hexdump(data, traw + b, traw + end, "func 0x%08X" % b)
        return 0

    for fva, (s, e) in REGIONS.items():
        hexdump(data, traw + s, traw + e, "region of func 0x%08X" % fva)
    return 0


if __name__ == "__main__":
    sys.exit(main())
