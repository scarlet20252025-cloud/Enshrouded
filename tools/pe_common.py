"""PE helpers shared by the WolfMount tools.

Everything here derives the section table from the PE header instead of a
hardcoded table, because a hand-copied table is how this project once lost a
day (the .rdata and .pdata values had been swapped by hand).

No third-party modules: only struct and the exe bytes.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common

DOS_MAGIC = b"MZ"
NT_MAGIC = b"PE\0\0"


def _u16(b, off):
    return struct.unpack_from("<H", b, off)[0]


def _u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def _u64(b, off):
    return struct.unpack_from("<Q", b, off)[0]


def sections(path):
    """Return [(name, va, raw_offset, raw_size, virtual_size), ...]."""
    b = open(path, "rb").read()
    if b[:2] != DOS_MAGIC:
        raise ValueError("not a PE image")
    e_lfanew = _u32(b, 0x3C)
    if b[e_lfanew:e_lfanew + 4] != NT_MAGIC:
        raise ValueError("no NT header")
    coff = e_lfanew + 4
    nsec = _u16(b, coff + 2)
    opt_size = _u16(b, coff + 16)
    opt = coff + 20
    magic = _u16(b, opt)
    pe32p = (magic == 0x20B)
    image_base = _u64(b, opt + 24) if pe32p else _u32(b, opt + 28)

    sec_table = opt + opt_size
    out = []
    for i in range(nsec):
        o = sec_table + i * 40
        name = b[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize = _u32(b, o + 8)
        va = _u32(b, o + 12)
        rsize = _u32(b, o + 16)
        raw = _u32(b, o + 20)
        out.append((name, image_base + va, raw, rsize, vsize))
    return out, image_base


def section(data, name):
    """Return (va, raw_offset, raw_size) for `name`, or None."""
    import io
    import tempfile
    # Reuse the header walk without touching the disk twice.
    if data[:2] != DOS_MAGIC:
        return None
    e_lfanew = _u32(data, 0x3C)
    if data[e_lfanew:e_lfanew + 4] != NT_MAGIC:
        return None
    coff = e_lfanew + 4
    nsec = _u16(data, coff + 2)
    opt_size = _u16(data, coff + 16)
    sec_table = coff + 20 + opt_size
    for i in range(nsec):
        o = sec_table + i * 40
        n = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        if n != name:
            continue
        va = _u32(data, o + 12)
        rsize = _u32(data, o + 16)
        raw = _u32(data, o + 20)
        return (va, raw, rsize)
    return None


def runtime_functions(data):
    """Return a sorted list of (begin_rva, end_rva) from .pdata."""
    p = section(data, ".pdata")
    if not p:
        return []
    _, raw, rsize = p
    out = []
    for i in range(0, rsize - 11, 12):
        b, e, _u = struct.unpack_from("<III", data, raw + i)
        if b == 0 and e == 0:
            continue
        if e <= b:
            continue
        out.append((b, e))
    out.sort()
    return out


def func_of(funcs, rva):
    """Binary-search the .pdata entry containing rva."""
    lo, hi = 0, len(funcs) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        b, e = funcs[mid]
        if rva < b:
            hi = mid - 1
        elif rva >= e:
            lo = mid + 1
        else:
            return (b, e)
    return None


if __name__ == "__main__":
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    secs, base = sections(exe)
    print("image base 0x%X" % base)
    for name, va, raw, rsize, vsize in secs:
        print("  %-8s va=0x%08X raw=0x%08X rsize=0x%08X vsize=0x%08X"
              % (name, va, raw, rsize, vsize))
