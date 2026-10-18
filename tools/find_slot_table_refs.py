"""Find every function that touches the ECS program slot table.

The registrar (0x1409d5770) stores each program descriptor into a slot array
reached with `leaq 0x746360(%rcx),%r14` and indexed with stride 0x1f20. So any
code that READS that array must also contain one of those two constants:

    disp32 0x746360 / 0x746350   — the slot array, relative to the registry
    imm32  0x1f20                — the slot stride

0x746360 is far too specific to appear by accident, so this is a much sharper
fingerprint than `callq *0x28(%reg)` (123 hits in 107 functions, useless).

The previous scan for stride 0x1f20 produced 22 sites, but NONE of them inside
the registrar itself — which proves the registrar reaches the array without a
stride immediate (it probably adds a pre-scaled offset, or uses a different
index expression). So the array base, not the stride, is the right search key.

Usage: python tools/find_slot_table_refs.py [--dis FUNC_RVA] [--dis-len N]
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

BASE_OFFSETS = [0x746360, 0x746350, 0x745A48, 0x745A58, 0x743B10]


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()

    secs, base = pe_common.sections(exe)
    text = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            text = (va, raw, rsize)
            break
    if text is None:
        raise SystemExit(".text not found")
    tva, traw, tsize = text
    print(".text va=0x%X raw=0x%X size=0x%X" % (tva, traw, tsize))

    funcs = pe_common.runtime_functions(data)
    print(".pdata runtime functions: %d\n" % len(funcs))

    # Every 4-byte window in .text that equals one of the base offsets. We do
    # not try to decode the instruction — the value is unique enough that a raw
    # scan is both sufficient and safer than a half-guessed opcode table.
    hits = {}
    for off in BASE_OFFSETS:
        needle = struct.pack("<I", off)
        for m in re.finditer(re.escape(needle), data[traw:traw + tsize]):
            rva = m.start()
            if rva in hits:
                hits[rva].append(off)
            else:
                hits[rva] = [off]

    if not hits:
        print("no reference to any slot-table base offset in .text")
        return 1

    print("%d site(s) referencing a slot-table base offset:" % len(hits))
    by_func = {}
    for rva in sorted(hits):
        f = pe_common.func_of(funcs, rva)
        fb = f[0] if f else None
        by_func.setdefault(fb, []).append((rva, hits[rva]))

    for fb in sorted(by_func, key=lambda x: (x is None, x)):
        sites = by_func[fb]
        if fb is None:
            for rva, offs in sites:
                print("  rva 0x%08X  ->  %s   (no .pdata bounds)"
                      % (rva, "/".join("0x%X" % o for o in offs)))
            continue
        size = None
        for b, e in funcs:
            if b == fb:
                size = e - b
                break
        print("\nfunc 0x%08X  (%s B)  %d site(s)"
              % (fb, size if size is not None else "?", len(sites)))
        for rva, offs in sites:
            print("    rva 0x%08X  ->  %s" % (rva, "/".join("0x%X" % o for o in offs)))

    # --dis support: dump the bytes around a chosen function so the caller can
    # eyeball whether it walks the array or just initialises it.
    args = sys.argv[1:]
    if "--dis" in args:
        i = args.index("--dis")
        if i + 1 >= len(args):
            raise SystemExit("--dis needs a function rva")
        target = int(args[i + 1], 0)
        length = 0x400
        if "--dis-len" in args:
            j = args.index("--dis-len")
            length = int(args[j + 1], 0)
        raw = traw + target
        chunk = data[raw:raw + length]
        print("\n--- bytes at func 0x%08X (%d bytes) ---" % (target, len(chunk)))
        for k in range(0, len(chunk), 16):
            row = chunk[k:k + 16]
            hexs = " ".join("%02X" % b for b in row)
            asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
            print("  0x%08X  %-47s  %s" % (target + k, hexs, asc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
