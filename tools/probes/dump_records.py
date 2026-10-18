r"""Decode the behaviour-descriptor records in .rdata at 0x141e2b690.

Observed layout is a 0x30-byte (or similar) struct:
  +0x00 fnptr          +0x08 flags/ptr     +0x10 u32   +0x18 u32 ...
Print the region as fixed 0x30 records with every field decoded (fn / string /
number) so we can read all behaviour entries and their component name lists.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

START_VA = 0x141E2B400
END_VA = 0x141E2BC00
REC = 0x30


def read_cstr(data, secs, va):
    fo = S.va_to_off(secs, va)
    if fo is None:
        return None
    end = data.find(b"\0", fo, fo + 200)
    if end < 0:
        return None
    try:
        s = data[fo:end].decode("ascii")
    except UnicodeDecodeError:
        return None
    if len(s) >= 2 and all(32 <= ord(c) < 127 for c in s):
        return s
    return None


def main():
    data = S.load()
    secs = S.sections(data)
    off = S.va_to_off(secs, START_VA)
    end = S.va_to_off(secs, END_VA)
    if off is None or end is None:
        print("bad range")
        return
    tlo = next(s["va"] for s in secs if s["name"] == ".text")
    thi = tlo + next(s["rawsize"] for s in secs if s["name"] == ".text")
    for base in range(off, end - REC + 1, REC):
        va = S.off_to_va(secs, base)
        print("--- rec rva=%#x" % va)
        for k in range(REC // 8):
            q = struct.unpack_from("<Q", data, base + k * 8)[0]
            note = ""
            if tlo <= q - S.IMAGE_BASE < thi:
                note = "FN  %#x" % (q - S.IMAGE_BASE)
            else:
                s = read_cstr(data, secs, q)
                if s:
                    note = "STR %r" % s
                elif q < 0x10000:
                    note = "u32=%d" % q
            if note:
                print("   +%02x  %016x  %s" % (k * 8, q, note))


if __name__ == "__main__":
    main()
