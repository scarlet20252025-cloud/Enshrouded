r"""Enumerate the event/message handler registry.

The tame handler cluster (0x47fb5b..0x4843ad) has zero direct callers and no
vtable references, so it is reached through a *registration descriptor* built at
startup. Look for the pattern the game uses elsewhere: a small array of
{fnptr, name-string-ptr, size} triples. Search .rdata/.data for any qword that
points INTO the cluster range, then dump a window of qwords around each hit so
we can read the record layout.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

CLUSTER = (S.IMAGE_BASE + 0x47F700, S.IMAGE_BASE + 0x484500)


def main():
    data = S.load()
    secs = S.sections(data)
    for sec in secs:
        if sec["name"] not in (".rdata", ".data"):
            continue
        i = sec["raw"]
        hi = sec["raw"] + sec["rawsize"]
        while i + 8 <= hi:
            v = struct.unpack_from("<Q", data, i)[0]
            if CLUSTER[0] <= v < CLUSTER[1]:
                rva = S.IMAGE_BASE + sec["va"] + (i - sec["raw"])
                print("=== %s rva=%#x -> func rva=%#x" % (sec["name"], rva, v - S.IMAGE_BASE))
                # Dump 8 qwords before and 8 after.
                base = i - 8 * 8
                for k in range(-8, 9):
                    o = base + k * 8
                    if o < sec["raw"] or o + 8 > hi:
                        continue
                    q = struct.unpack_from("<Q", data, o)[0]
                    orva = S.IMAGE_BASE + sec["va"] + (o - sec["raw"])
                    note = ""
                    if S.IMAGE_BASE <= q < S.IMAGE_BASE + 0x142A0000:
                        note = "  <- ptr into image"
                    print("   %+#3d  rva=%#x  %016x%s" % (k, orva, q, note))
                print()
            i += 8


if __name__ == "__main__":
    main()
