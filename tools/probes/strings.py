#!/usr/bin/env python3
"""Extract ASCII strings from enshrouded.exe (all sections) with their RVAs.

Used to locate console/command text: command names, help strings, admin verbs.
"""
import re
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


def main(patterns):
    data = open(EXE, "rb").read()
    secs = sections(data)
    rx = re.compile("|".join(patterns), re.IGNORECASE) if patterns else None
    count = 0
    for nm, va, vs, raw, rs in secs:
        blob = data[raw:raw + rs]
        for m in re.finditer(rb"[\x20-\x7e]{5,120}", blob):
            s = m.group().decode("ascii")
            if rx and not rx.search(s):
                continue
            rva = IMAGE + va + m.start()
            print("0x%X  %-8s %s" % (rva, nm, s))
            count += 1
            if count > 20000:
                print("... truncated")
                return


if __name__ == "__main__":
    main(sys.argv[1:])
