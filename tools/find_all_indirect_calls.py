"""Find the program-handler call: any `call [mem]` whose displacement, combined
with a nearby `imul reg,reg,0x1F20` and a slot base, resolves to slot+0x28.

Earlier scans only covered `call [reg+0x28]` with mod=01 (disp8). The real call
could be:
  * `call [reg+disp32]`   (mod=10, disp32)  -> 48/49 FF 52 28 00 00 00 style
  * `call [reg]`          (mod=00)          -> 48/49 FF 10 / FF 11 ...
  * `call [reg+0x28]` after `mov rax,[slot+0x28]` then `call rax`
  * `call qword [rax+rax*8+0x28]` style indexed forms

This tool enumerates every `FF /2` (indirect call) in the whole .text with its
full modrm/SIB/displacement so we can filter by hand.

Usage: python tools/find_all_indirect_calls.py [--func 0xXXXX]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

STRIDE = 0x1F20
BASES = (0x746360, 0x745A28)


def scan_calls(text, start, end):
    """Yield (rva, length, modrm, sib, disp, kind) for every FF /2 in [start,end)."""
    i = start
    while i < end - 1:
        if text[i] != 0xFF:
            i += 1
            continue
        # allow a REX prefix immediately before
        j = i + 1
        modrm = text[j]
        if (modrm & 0x38) != 0x10:  # /2 = call
            i += 1
            continue
        mod = modrm >> 6
        rm = modrm & 7
        length = 2
        sib = None
        disp = 0
        kind = "call"
        if mod == 0:
            if rm == 5:
                disp = struct.unpack_from("<i", text, j + 1)[0]
                length = 6
                kind = "call[rip+disp32]"
            elif rm == 4:
                sib = text[j + 1]
                base = sib & 7
                if base == 5:
                    if mod == 0:
                        disp = struct.unpack_from("<i", text, j + 2)[0]
                        length = 7
                        kind = "call[sib+disp32]"
                    else:
                        disp = struct.unpack_from("<i", text, j + 2)[0]
                        length = 7
                        kind = "call[sib+disp32]"
                else:
                    length = 3
                    kind = "call[sib]"
            else:
                length = 2
                kind = "call[reg]"
        elif mod == 1:
            disp = struct.unpack_from("<b", text, j + 1)[0]
            if rm == 4:
                sib = text[j + 1]
                disp = struct.unpack_from("<i", text, j + 2)[0] if (sib & 7) == 5 else disp
                length = 4 if (sib & 7) != 5 else 7
                kind = "call[sib+disp]"
            else:
                length = 3
                kind = "call[reg+disp8]"
        elif mod == 2:
            if rm == 4:
                sib = text[j + 1]
                disp = struct.unpack_from("<i", text, j + 2)[0]
                length = 7
                kind = "call[sib+disp32]"
            else:
                disp = struct.unpack_from("<i", text, j + 1)[0]
                length = 6
                kind = "call[reg+disp32]"
        else:
            length = 2
            kind = "call[reg]"
        yield (i, length, modrm, sib, disp, kind)
        i += 1


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = tsize = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw, tsize = raw, rsize
            break
    text = data[traw:traw + tsize]
    funcs = pe_common.runtime_functions(data)

    want_func = None
    if "--func" in sys.argv:
        want_func = int(sys.argv[sys.argv.index("--func") + 1], 0)

    total = 0
    disp28 = []
    in_stride_func = []
    for rva, length, modrm, sib, disp, kind in scan_calls(text, 0, tsize):
        total += 1
        f = pe_common.func_of(funcs, rva)
        fb = f[0] if f else None
        if disp == 0x28:
            disp28.append((rva, fb, modrm, sib, kind))
        if fb is not None and want_func == fb:
            disp28.append((rva, fb, modrm, sib, kind))
    print("total FF /2 indirect calls in .text: %d" % total)
    print("with disp == 0x28: %d" % len(disp28))
    for rva, fb, modrm, sib, kind in disp28:
        print("  0x%08X  func %-12s modrm %02X sib %s  %s"
              % (rva, ("0x%08X" % fb) if fb else "?", modrm,
                 ("%02X" % sib) if sib is not None else "--", kind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
