r"""Read .pdata to get the true function bounds for the call28 candidate sites,
then re-examine only those functions that are large enough to be a dispatcher.

.pdata is an array of RUNTIME_FUNCTION { ULONG BeginAddress; ULONG EndAddress;
ULONG UnwindInfoAddress; } (12 bytes each), addresses are RVAs.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
import struct
import sys

sys.path.insert(0, os.path.join(ROOT, "tools"))
import scanrefs as S  # noqa: E402

CANDIDATES = [0x36789, 0x38F4D, 0x3943C, 0x43C13, 0x5404A7, 0x540772,
              0x540B71, 0x542418, 0x5425F8, 0x54439C, 0x550E9B, 0x551719,
              0x552466, 0x559542, 0x55E21C, 0x55E538, 0x55ECF9, 0x55F46E,
              0x5600B0, 0x560330, 0x56081E, 0x5648C4, 0x565FFB, 0x56619C]


def main():
    data = S.load()
    secs = S.sections(data)
    pd = next(s for s in secs if s["name"] == ".pdata")
    n = pd["rawsize"] // 12
    print("pdata entries:", n)

    funcs = []
    for i in range(n):
        beg, end, unw = struct.unpack_from("<III", data, pd["raw"] + i * 12)
        if beg == 0 and end == 0:
            continue
        funcs.append((beg, end))
    funcs.sort()
    print("valid runtime functions:", len(funcs))

    for c in CANDIDATES:
        lo, hi = 0, len(funcs) - 1
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            if funcs[mid][0] <= c:
                best = funcs[mid]
                lo = mid + 1
            else:
                hi = mid - 1
        if best and best[0] <= c < best[1]:
            print("cand %#x -> func %#x..%#x  size=%d" % (
                c, best[0], best[1], best[1] - best[0]))
        else:
            print("cand %#x -> no enclosing .pdata entry (mid-instruction site)" % c)


if __name__ == "__main__":
    main()
