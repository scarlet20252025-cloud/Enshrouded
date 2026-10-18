r"""Dump the handler descriptor table in .rdata around 0x141e2b690.

Records appear to be groups of {string, string, string, fnptr}. Decode the whole
region so we can read the layout and count entries. This table is the link
between event/message type NAMES and handler functions - i.e. the registration
mechanism the game itself uses.
"""
import bisect
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

START = 0x141E2B690
END = 0x141E2BD00


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


def fn_rva(data, secs, v):
    """Return rva if v points into .text."""
    fo = S.va_to_off(secs, v)
    if fo is None:
        return None
    for s in secs:
        if s["name"] == ".text" and s["va"] <= v - S.IMAGE_BASE < s["va"] + max(s["vsize"], s["rawsize"]):
            return v - S.IMAGE_BASE
    return None


def main():
    data = S.load()
    secs = S.sections(data)
    for s in secs:
        if s["name"] == ".rdata":
            print("rdata: va=%#x..%#x" % (s["va"], s["va"] + s["vsize"]))
    # 0x141e2b690 is a full VA; translate by removing IMAGE_BASE.
    off = S.va_to_off(secs, START)
    end = S.va_to_off(secs, END)
    if off is None or end is None:
        print("range outside raw sections")
        return
    i = off
    while i + 8 <= end:
        va = S.IMAGE_BASE + START + (i - off)
        v = struct.unpack_from("<Q", data, i)[0]
        s = read_cstr(data, secs, v)
        fr = fn_rva(data, secs, v)
        tag = ""
        if s:
            tag = "STR  %r" % s
        elif fr:
            tag = "FN   %#x" % fr
        elif v == 0:
            tag = ""
        else:
            tag = "0x%x" % v
        print("%#x  %016x  %s" % (va, v, tag))
        i += 8


if __name__ == "__main__":
    main()
