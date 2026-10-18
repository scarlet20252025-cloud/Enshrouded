r"""For each of the 16 descriptors, dump the full 0x190 bytes and decode what
comes after the group terminator. We need to know what lives at +0x180/+0x184
(the fields copied to slot+0x20/+0x24) and whether there is a group COUNT field
somewhere.

Print hex + qword/dword interpretation of [term_off .. 0x190].
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE
THUNKS = [0x12CF5C0 + 0x10 * i for i in range(16)]


def desc_va_of(data, secs, t):
    va = IB + t
    off = S.va_to_off(secs, va)
    rel = struct.unpack_from("<i", data, off + 3)[0]
    return va + 7 + rel


def main():
    data = S.load()
    secs = S.sections(data)
    for t in THUNKS:
        d = desc_va_of(data, secs, t)
        off = S.va_to_off(secs, d)
        np_, nl, h = struct.unpack_from("<QQQ", data, off)
        no = S.va_to_off(secs, np_)
        nm = data[no:no + 40].split(b"\0")[0].decode("latin1")
        print("=" * 70)
        print("%s  desc=%s handler=%s" % (nm, hex(d - IB), hex(h - IB)))
        # walk groups
        o = off + 0x18
        g = 0
        while True:
            pool, count, pad = struct.unpack_from("<QII", data, o)
            a, b, c = struct.unpack_from("<QII", data, o + 0x10)
            g += 1
            if pool == 0 and count == 0 and a == 0 and b == 0:
                break
            o += 0x10
            if g > 40:
                break
        tail_start = (o + 0x10) - off
        print("  terminator at +%#x, tail dump:" % tail_start)
        for i in range(tail_start, 0x190, 8):
            q = struct.unpack_from("<Q", data, off + i)[0]
            extra = ""
            if 0 < q < 0x142A00000:
                extra = "  (u32 pair: %d / %d)" % (q & 0xFFFFFFFF, q >> 32)
            print("    +%#04x  %016x%s" % (i, q, extra))


if __name__ == "__main__":
    main()
