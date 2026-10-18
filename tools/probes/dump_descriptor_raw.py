r"""Decode the wildlife_enemy_transformer descriptor groups (thunk 0x12cf630 ->
descriptor 0x141e2b860). The generic loop stopped after the name because the
group pointers are non-zero but point outside the flat name pool. Print raw
qwords from descriptor+0x18 to descriptor+0x60 so the real layout is visible.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import scanrefs as S  # noqa: E402

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IB = S.IMAGE_BASE
TARGETS = [0x1E2B860, 0x1E2BA50, 0x1E2B680]


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


def main():
    data = open(EXE, "rb").read()
    secs = S.sections(data)
    for rva in TARGETS:
        off = rva2off(secs, rva)
        print("=" * 74)
        print("descriptor rva=%#x" % rva)
        for i in range(0, 0x70, 8):
            v = struct.unpack_from("<Q", data, off + i)[0]
            extra = ""
            if v == 0:
                extra = "0"
            elif IB + 0x1000 <= v < IB + 0x1700000:
                s = cstr(data, secs, v)
                if s:
                    extra = "str %r" % s
                elif rva2off(secs, v - IB) is not None:
                    extra = "ptr rva=%#x" % (v - IB)
            print("  +0x%02x  %#018x  %s" % (i, v, extra))


if __name__ == "__main__":
    main()
