r"""Decode the flat component-name pool at rva 0x1e2b400..0x1e2b690 and print the
groups for wildlife_enemy_transformer (0x1e2b808 / 0x1e2b818) explicitly.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import scanrefs as S  # noqa: E402

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IB = S.IMAGE_BASE


def rva2off(secs, rva):
    for s in secs:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
            return s["raw"] + (rva - s["va"])
    return None


def cstr(data, secs, va):
    off = rva2off(secs, va - IB)
    if off is None:
        return None
    end = data.find(b"\0", off)
    if end < 0 or end - off > 200:
        return None
    try:
        return data[off:end].decode("utf-8")
    except UnicodeDecodeError:
        return None


def pool_names(data, secs, ptr, cnt):
    off = rva2off(secs, ptr - IB)
    out = []
    for j in range(cnt):
        np_ = struct.unpack_from("<Q", data, off + j * 16)[0]
        out.append(cstr(data, secs, np_))
    return out


def main():
    data = open(EXE, "rb").read()
    secs = S.sections(data)

    print("=== wildlife_enemy_transformer groups ===")
    for rva, cnt in [(0x1E2B808, 1), (0x1E2B818, 3)]:
        print("  rva=%#x n=%d: %s" % (rva, cnt, pool_names(data, secs, IB + rva, cnt)))

    print()
    print("=== full flat pool 0x1e2b400..0x1e2b690 ===")
    off = rva2off(secs, 0x1E2B400)
    for i in range(0, 0x290, 16):
        ptr, ln, pad = struct.unpack_from("<QII", data, off + i)
        if ptr == 0 and ln == 0:
            continue
        s = cstr(data, secs, ptr)
        print("  rva=%#x  len=%-3d %r" % (0x1E2B400 + i, ln, s))


if __name__ == "__main__":
    main()
