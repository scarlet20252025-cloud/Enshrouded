#!/usr/bin/env python3
"""Dump a VA region as hex + ascii, and decode qword pointer tables."""
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


def va2off(secs, va):
    rva = va - IMAGE if va >= IMAGE else va
    for nm, sva, vs, raw, rs in secs:
        if sva <= rva < sva + rs:
            return raw + (rva - sva)
    return None


def cstr(data, off):
    e = data.find(b"\0", off)
    if e < 0 or e - off > 200:
        return None
    try:
        return data[off:e].decode("ascii")
    except UnicodeDecodeError:
        return None


def main(va, length="0x200"):
    data = open(EXE, "rb").read()
    secs = sections(data)
    start = int(va, 16)
    n = int(length, 16)
    print("--- raw dump ---")
    for row in range(0, n, 16):
        off = va2off(secs, start + row)
        if off is None:
            break
        chunk = data[off:off + 16]
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        print("%X  %s  %s" % (start + row, " ".join("%02x" % b for b in chunk), asc))
    print("--- qword decode ---")
    for row in range(0, n, 8):
        off = va2off(secs, start + row)
        if off is None or off + 8 > len(data):
            break
        q = struct.unpack_from("<Q", data, off)[0]
        note = ""
        if IMAGE <= q < IMAGE + 0x2000000:
            so = va2off(secs, q)
            if so is not None:
                s = cstr(data, so)
                if s and len(s) >= 2:
                    note = '  -> "%s"' % s
        print("%X  %016X%s" % (start + row, q, note))


if __name__ == "__main__":
    main(*sys.argv[1:])
