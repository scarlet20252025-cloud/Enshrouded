r"""Check whether the tame cluster is reached indirectly through the
enclosing runtime function table (C++ virtual dispatch on a behaviour object).

Print the .pdata function that contains each cluster function and check for a
vtable: a run of qword pointers into .text that includes the cluster addresses.
We look for any qword in .rdata/.data that equals 0x47fb5b+base, then dump the
surrounding qword array and resolve each entry to a function name via .pdata.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

CLUSTER = [0x47FB5B, 0x47FB63, 0x47FB73, 0x47FC97, 0x480341, 0x480559,
           0x4806A0, 0x48072A, 0x480772, 0x481830, 0x481955, 0x483800,
           0x484185, 0x484220, 0x4843AD, 0x4820E1, 0x47F730, 0x47F8A0]


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)

    # Build a sorted list of function starts for name resolution.
    starts = sorted(set(b for b, _ in funcs))
    import bisect

    def fname(addr):
        k = bisect.bisect_right(starts, addr) - 1
        if k < 0:
            return None
        b = starts[k]
        if b <= addr < funcs[funcs.index((b, next(e for bb, e in funcs if bb == b)))]:
            return b
        return None

    # Find qwords equal to any cluster address in .rdata / .data.
    want = set(S.IMAGE_BASE + a for a in CLUSTER)
    for sec in secs:
        if sec["name"] not in (".rdata", ".data"):
            continue
        i = sec["raw"]
        hi = sec["raw"] + sec["rawsize"]
        found = 0
        while i + 8 <= hi:
            v = struct.unpack_from("<Q", data, i)[0]
            if v in want:
                print("qword ref: %s rva=%#x -> func rva=%#x" % (
                    sec["name"], S.IMAGE_BASE + sec["va"] + (i - sec["raw"]),
                    v - S.IMAGE_BASE))
                found += 1
                if found > 40:
                    break
            i += 8


if __name__ == "__main__":
    main()
