"""List .pdata runtime functions overlapping a range.

Written because .pdata for this image splits what looks like one function into
several consecutive entries. Querying "the function containing 0x97B790" returns
a 300-byte entry, but the real body -- the one that iterates the component array
and reads the template GUID -- starts at 0x97B8BC and runs to 0x97D358. Any
conclusion drawn from the 300-byte entry alone is a conclusion about a fragment.

Use this to see every entry in a window before disassembling any of them.

Usage: python tools/pdata_range.py 0x97B790 0x97C500
"""
import struct
import sys

import common
EXE = common.exe_path()
if not EXE:
    raise SystemExit(
        'enshrouded.exe not found; set WOLFMOUNT_EXE or ENSHROUDED_EXE'
        ' to the full path')
PDATA_VA, PDATA_SIZE, PDATA_RAW = 0x2836000, 0xD4FC4, 0x1FCEA00


def main():
    lo = int(sys.argv[1], 0)
    hi = int(sys.argv[2], 0) if len(sys.argv) > 2 else lo + 0x1000

    blob = open(EXE, "rb").read()[PDATA_RAW:PDATA_RAW + PDATA_SIZE]
    entries = []
    for off in range(0, len(blob) - 11, 12):
        begin, end, unwind = struct.unpack_from("<III", blob, off)
        if end >= lo and begin <= hi:
            entries.append((begin, end, unwind))

    entries.sort()
    print("%d runtime function(s) overlapping 0x%X..0x%X" % (len(entries), lo, hi))
    for begin, end, unwind in entries:
        print("  begin=%08X  end=%08X  size=%-6d  unwind=%08X"
              % (begin, end, end - begin, unwind))
    return 0


if __name__ == "__main__":
    sys.exit(main())
