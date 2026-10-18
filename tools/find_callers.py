"""Find every caller of a function, by scanning .text for E8/E9 rel32.

The PE has no symbol table, so "who calls 0x9D46E0" cannot be answered from
metadata. A direct call is `E8 rel32` (call) or `E9 rel32` (jmp); the target is
`next_instruction + rel32`. We scan the whole .text for both and report each
hit with the .pdata function that contains it.

Usage: python tools/find_callers.py RVA [RVA ...]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    targets = []
    for a in sys.argv[1:]:
        targets.append(int(a, 0))
    if not targets:
        raise SystemExit("usage: find_callers.py RVA [RVA ...]")

    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = tsize = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw, tsize = raw, rsize
            break
    text = data[traw:traw + tsize]
    funcs = pe_common.runtime_functions(data)

    for target in targets:
        hits = []
        i = 0
        n = len(text)
        while i < n - 5:
            op = text[i]
            if op == 0xE8 or op == 0xE9:
                rel = struct.unpack_from("<i", text, i + 1)[0]
                dest = (i + 5 + rel) & 0xFFFFFFFF
                if dest == target:
                    hits.append((i, "call" if op == 0xE8 else "jmp"))
            i += 1
        print("=== callers of rva 0x%08X : %d ===" % (target, len(hits)))
        by_func = {}
        for rva, kind in hits:
            f = pe_common.func_of(funcs, rva)
            by_func.setdefault(f[0] if f else None, []).append((rva, kind))
        for fb in sorted(by_func, key=lambda x: (x is None, x)):
            if fb is None:
                for rva, kind in by_func[fb]:
                    print("   %s @ 0x%08X  (no .pdata bounds)" % (kind, rva))
                continue
            size = None
            for b, e in funcs:
                if b == fb:
                    size = e - b
                    break
            print("   func 0x%08X (%s B):" % (fb, size))
            for rva, kind in by_func[fb]:
                print("      %s @ 0x%08X" % (kind, rva))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
