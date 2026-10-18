r"""Print the strings around 0x141d5fae8 and 0x141d5fb18, and 0x141d5e6c8,
0x141d5e6d8 (the movups/movsd constants), to identify what 0x1409d5770 builds."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scanrefs as S  # noqa: E402

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IB = S.IMAGE_BASE
RVAS = [0x1D5FAE8, 0x1D5FB18, 0x1D5E6C8, 0x1D5E6D8, 0x1D5FAC0, 0x1D5FB60]


def rva2off(secs, rva):
    for s in secs:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
            return s["raw"] + (rva - s["va"])
    return None


def main():
    data = open(EXE, "rb").read()
    secs = S.sections(data)
    for rva in RVAS:
        off = rva2off(secs, rva)
        if off is None:
            print("rva=%#x unmapped" % rva)
            continue
        blob = data[off:off + 64]
        print("rva=%#x hex=%s" % (rva, blob.hex()))
        # try utf-8 strings of length>=4
        s = blob.split(b"\0")[0]
        if 4 <= len(s) <= 60:
            try:
                print("        str=%r" % s.decode("utf-8"))
            except UnicodeDecodeError:
                pass
        print("        qwords=%s" % [hex(v) for v in struct.unpack_from("<QQQQQQQQ", data, off)])
        print("        dwords=%s" % (struct.unpack_from("<IIIIIIIIIIIIIIII", data, off),))
        print()


if __name__ == "__main__":
    main()
