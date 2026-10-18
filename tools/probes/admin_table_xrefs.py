r"""Admin commands have ZERO .text references by type hash. They are deserialized
by reflection index, not by hash. Find the deserialization/dispatch instead.

Approach: the command-name strings ("adminSpawnCommand") live at 0x141507780+.
Who references those string pointers? The table at 0x141507400 has char* name at
+0. Find xrefs to the TABLE base and to each name string; also check whether the
table is indexed by a loop (e.g. `lea rcx,[table + i*0x40]`).

More promising: find the reflection TYPE INDEX for AdminSpawnCommand (idx 2887)
and search for the immediate 0xB47 (2887) in .text — the deserializer may switch
on the type index.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE
TABLE = IB + 0x1507400
NAMES_RVA = 0x1507780
ADMIN_IDX = 2887  # AdminSpawnCommand


def main():
    data = S.load()
    secs = S.sections(data)

    # 1) absolute u64 refs to the table base anywhere in the image
    for label, target in [("table base 0x1507400", TABLE),
                          ("table 2nd copy 0x18D3410", IB + 0x18D3410),
                          ("names 0x1507780", IB + NAMES_RVA)]:
        pat = struct.pack("<Q", target)
        found = []
        for s in secs:
            i = s["raw"]
            end = s["raw"] + s["rawsize"]
            while True:
                i = data.find(pat, i, end)
                if i < 0:
                    break
                found.append("%s rva=%#x" % (s["name"], IB + s["va"] + (i - s["raw"])))
                i += 1
        print("%s -> %d refs" % (label, len(found)))
        for f in found[:12]:
            print("    " + f)
        print()

    # 2) immediate 2887 / 0xB47 in .text
    lo, hi = S.text_span(secs)
    tlo = IB + next(s["va"] for s in secs if s["name"] == ".text")
    hits = []
    for i in range(lo, hi - 4):
        if struct.unpack_from("<I", data, i)[0] == ADMIN_IDX:
            hits.append(tlo + (i - lo))
    print("u32 2887 in .text: %d" % len(hits))
    for a in hits[:20]:
        print("   rva=%#x" % (a - IB))


if __name__ == "__main__":
    main()
