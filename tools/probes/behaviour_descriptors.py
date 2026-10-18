r"""For each of the 16 behaviour descriptors, print its FN pointer and name strings.

This gives the complete list of ECS "systems/behaviours" the game registers,
including the wildlife transformers we care about. If the tame/wildlife
behaviour descriptor is one of these, we can read its layout to learn how to
inject our own.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

THUNKS = [0x12CF5C0, 0x12CF5D0, 0x12CF5E0, 0x12CF5F0, 0x12CF600, 0x12CF610,
          0x12CF620, 0x12CF630, 0x12CF640, 0x12CF650, 0x12CF660, 0x12CF670,
          0x12CF680, 0x12CF690, 0x12CF6A0, 0x12CF6B0]


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
    tsec = next(s for s in secs if s["name"] == ".text")
    for trva in THUNKS:
        off = tsec["raw"] + (trva - tsec["va"])
        b = data[off:off + 8]
        rel = struct.unpack_from("<i", b, 3)[0]
        tgt = S.IMAGE_BASE + trva + 7 + rel
        desc = tgt - S.IMAGE_BASE
        fo = S.va_to_off(secs, tgt)
        if fo is None:
            print("thunk %#x -> %#x  (unresolved)" % (trva, desc))
            continue
        print("=== descriptor rva=%#x" % desc)
        for k in range(0, 0x60, 8):
            q = struct.unpack_from("<Q", data, fo + k)[0]
            s = read_cstr(data, secs, q)
            fn = (S.IMAGE_BASE + next(x["va"] for x in secs if x["name"] == ".text")
                  <= q < S.IMAGE_BASE + next(x["va"] + x["rawsize"] for x in secs if x["name"] == ".text"))
            tag = "FN %#x" % (q - S.IMAGE_BASE) if fn else (("STR %r" % s) if s else "")
            if tag or q:
                print("   +%02x %016x  %s" % (k, q, tag))


if __name__ == "__main__":
    main()
