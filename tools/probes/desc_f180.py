r"""The registrar 0x1409d5770 reads descriptor+0x180 BEFORE reading the group
list. But descriptors are only ~0x190 bytes and 0x180 is inside. Our descriptor
dump shows +0x180 = 0x0000000100000601 (low u32 = 0x601, high u32 = 1) for
extinguish_client, and +0x188 = a pointer.

Let's dump +0x170..0x190 for ALL 16 descriptors and also compare with the two
transformer descriptors, to learn what +0x180/+0x184 must contain for a
synthetic descriptor.
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
    print("%-32s %-18s %-18s %-12s" % ("name", "+0x180", "+0x188", "groups"))
    for t in THUNKS:
        d = desc_va_of(data, secs, t)
        off = S.va_to_off(secs, d)
        np_, nl, h = struct.unpack_from("<QQQ", data, off)
        no = S.va_to_off(secs, np_)
        nm = data[no:no + 40].split(b"\0")[0].decode("latin1")
        f180, f184 = struct.unpack_from("<II", data, off + 0x180)
        p188 = struct.unpack_from("<Q", data, off + 0x188)[0]
        # count groups
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
        print("%-32s %08x/%08x      %-18s %d" % (nm, f180, f184, hex(p188), g - 1))


if __name__ == "__main__":
    main()
