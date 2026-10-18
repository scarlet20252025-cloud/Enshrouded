r"""Enumerate the 16 behaviour descriptors with names, handler RVAs and their
component-name groups. This is the authoritative registry map.

Thunks at .text rva 0x12cf5c0, stride 0x10, 8-byte `lea rax,[rip+d]; ret`
followed by int3 padding. Descriptor layout:
  +0x00 char* name
  +0x08 u64   nameLen
  +0x10 void* handler
  +0x18 ...   {char** names; u32 count} pairs until 0
Names point into a flat 16-byte pool of {char*, u32 len, u32 pad}.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import scanrefs as S  # noqa: E402

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
THUNK_RVA = 0x12CF5C0
N = 16
STRIDE = 0x10
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


def main():
    data = open(EXE, "rb").read()
    secs = S.sections(data)

    # 1) decode the thunks
    descs = []
    for i in range(N):
        ta = THUNK_RVA + i * STRIDE
        off = rva2off(secs, ta)
        b = data[off:off + 8]
        if b[0:3] != b"\x48\x8d\x05" or b[7] != 0xC3:
            print("thunk %d not lea/ret: %s" % (i, b.hex()))
            continue
        rel = struct.unpack_from("<i", b, 3)[0]
        target = IB + ta + 7 + rel
        descs.append((IB + ta, target))

    print("thunks decoded: %d" % len(descs))
    print()

    # 2) decode each descriptor
    for ta, dv in descs:
        off = rva2off(secs, dv - IB)
        if off is None:
            continue
        namep, namelen, handler = struct.unpack_from("<QQQ", data, off)
        name = cstr(data, secs, namep)
        groups = []
        p = off + 0x18
        for _ in range(12):
            ptr, cnt = struct.unpack_from("<QI", data, p)
            if ptr == 0 and cnt == 0:
                break
            names = []
            noff = rva2off(secs, ptr - IB)
            if noff is None:
                groups.append((ptr, cnt, ["<bad ptr>"]))
            else:
                for j in range(cnt):
                    np_, nl, _pad = struct.unpack_from("<QII", data, noff + j * 16)
                    s = cstr(data, secs, np_)
                    names.append(s if s is not None else "?")
                groups.append((ptr, cnt, names))
            p += 16
        print("descriptor rva=%#x  thunk rva=%#x" % (dv - IB, ta - IB))
        print("   name=%r len=%d" % (name, namelen))
        print("   handler rva=%#x" % (handler - IB))
        for va, cnt, names in groups:
            print("   group rva=%#x n=%d: %s" % (va - IB, cnt, ", ".join(names)))
        print()


def secs_off_to_va(secs, off):
    for s in secs:
        if s["raw"] <= off < s["raw"] + s["rawsize"]:
            return IB + s["va"] + (off - s["raw"])
    return 0


if __name__ == "__main__":
    main()
