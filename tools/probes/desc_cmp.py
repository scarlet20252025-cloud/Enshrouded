r"""Compare the two transformer descriptors byte-for-byte over 0x190 bytes to
find the real differences (beyond the group list). Also dump the `wildlife`
descriptor fully. We want to know the minimal viable descriptor we could
synthesize and pass to the registrar 0x1409d5770.

Also print the descriptor-adjacent strings (the component name pool entries the
transformers point at) to confirm what the group pools contain.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE


def desc_va_of(data, secs, t):
    va = IB + t
    off = S.va_to_off(secs, va)
    rel = struct.unpack_from("<i", data, off + 3)[0]
    return va + 7 + rel


def cstr(data, secs, p):
    if p == 0:
        return "<null>"
    o = S.va_to_off(secs, p)
    return data[o:o + 48].split(b"\0")[0].decode("latin1")


def dump(data, secs, d, label):
    off = S.va_to_off(secs, d)
    np_, nl, h = struct.unpack_from("<QQQ", data, off)
    print("=" * 72)
    print("%s  desc=%#x  handler=%#x  nameLen=%d" % (label, d - IB, h - IB, nl))
    o = off + 0x18
    g = 0
    while True:
        pool, count, pad = struct.unpack_from("<QII", data, o)
        a, b, c = struct.unpack_from("<QII", data, o + 0x10)
        names = []
        for i in range(count):
            ep, elen, epad = struct.unpack_from("<QII", data, S.va_to_off(secs, pool) + i * 16)
            names.append(cstr(data, secs, ep))
        print("  group%d +%#04x n=%d : %s" % (g, (o - off), count, names))
        g += 1
        if pool == 0 and count == 0 and a == 0 and b == 0:
            break
        o += 0x10
        if g > 20:
            break
    print("  --- fields ---")
    for i in range(0, 0x190, 8):
        q = struct.unpack_from("<Q", data, off + i)[0]
        ann = ""
        if q > 0x140000000 and q < 0x142A00000:
            ann = "  -> %s" % cstr(data, secs, q)
        elif 0 < q < 0x10000:
            ann = "  (u32: %d)" % q
        print("    +%#04x %016x%s" % (i, q, ann))


def main():
    data = S.load()
    secs = S.sections(data)
    a = desc_va_of(data, secs, 0x12CF630)  # wildlife_enemy_transformer
    b = desc_va_of(data, secs, 0x12CF640)  # wildlife_farm_animal_transformer
    dump(data, secs, a, "wildlife_enemy_transformer")
    dump(data, secs, b, "wildlife_farm_animal_transformer")


if __name__ == "__main__":
    main()
