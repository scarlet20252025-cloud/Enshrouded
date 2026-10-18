#!/usr/bin/env python3
"""Find references (absolute 8-byte pointers and lea rel32) to a target VA."""
import struct
import sys

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IMAGE = 0x140000000


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    base = pe + 24 + optsz
    out = []
    for i in range(nsec):
        o = base + i * 40
        nm = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        vs, va, rs, raw = struct.unpack_from("<IIII", data, o + 8)
        out.append((nm, va, vs, raw, rs))
    return out


def main(targets):
    data = open(EXE, "rb").read()
    secs = sections(data)
    for t in targets:
        tva = int(t, 16)
        if tva >= IMAGE:
            tva -= IMAGE
        print("=== refs to VA 0x%X ===" % (IMAGE + tva))
        found = 0
        pat = struct.pack("<Q", IMAGE + tva)
        for nm, va, vs, raw, rs in secs:
            blob = data[raw:raw + rs]
            i = blob.find(pat)
            while i >= 0:
                print("   ptr  %-8s 0x%X" % (nm, IMAGE + va + i))
                found += 1
                i = blob.find(pat, i + 1)
        # lea rel32: 48 8D xx <rel32>  -> target
        for nm, va, vs, raw, rs in secs:
            if nm != ".text":
                continue
            blob = data[raw:raw + rs]
            for i in range(len(blob) - 7):
                if blob[i] == 0x48 and blob[i + 1] == 0x8D:
                    modrm = blob[i + 2]
                    if (modrm & 0xC7) != 0x05:
                        continue
                    rel = struct.unpack_from("<i", blob, i + 3)[0]
                    insn = IMAGE + va + i
                    if insn + 7 + rel == IMAGE + tva:
                        print("   lea  .text    0x%X" % insn)
                        found += 1
        if not found:
            print("   (none)")


if __name__ == "__main__":
    main(sys.argv[1:])
