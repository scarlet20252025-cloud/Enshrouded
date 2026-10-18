#!/usr/bin/env python3
"""For a set of component type names, report how the game writes them.

Classifies every .text reference to a component's qualifiedHash as either:
  ENQUEUE  - routed through Enqueue (0x140952400): record shape
             {u16 size; u8 flags; u8; u16; u16; u32 eid} + payload at +0xC
  ARRAY    - built into a 24-byte descriptor {u32 hash; u64 ptr; u64 size}
             array submitted wholesale
  OTHER    - inlined into a larger prebuilt buffer
"""
import json
import struct
import sys

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
REFL = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"
IMAGE = 0x140000000

ENQUEUE = 0x140952400


def load_hashes():
    d = json.load(open(REFL, encoding="utf-8"))
    return {t["qualifiedName"]: t["qualifiedHash"] for t in d["types"]}


def main(names):
    data = open(EXE, "rb").read()
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    secoff = pe + 24 + optsz
    secs = []
    for i in range(nsec):
        o = secoff + i * 40
        nm = data[o:o + 8].rstrip(b"\0").decode("ascii", "replace")
        vs, va, rs, raw = struct.unpack_from("<IIII", data, o + 8)
        secs.append((nm, va, vs, raw, rs))

    text = next(s for s in secs if s[0] == ".text")
    _, tva, _, traw, trs = text
    tlo = IMAGE + tva
    hashes = load_hashes()

    for nm in names:
        h = hashes.get(nm)
        if h is None:
            print("%-42s NOT IN TABLE" % nm)
            continue
        pat = struct.pack("<I", h)
        hits = []
        for name, va, vs, raw, rs in secs:
            i = raw
            while True:
                i = data.find(pat, i, raw + rs)
                if i < 0:
                    break
                hits.append((name, IMAGE + va + (i - raw)))
                i += 1
        # classify .text hits by looking backwards for the Enqueue call
        kinds = []
        for name, v in hits:
            if name != ".text":
                continue
            off = traw + (v - tlo)
            back = data[max(0, off - 16):off]
            kind = "OTHER"
            if b"\xe8" in back:
                # find the rel32 call immediately preceding
                for j in range(len(back) - 5, -1, -1):
                    if back[j] == 0xE8:
                        rel = struct.unpack_from("<i", back, j + 1)[0]
                        site = tlo + (off - len(back) + j - traw + traw) - traw + traw
                        site = (IMAGE + tva) + ((off - len(back) + j) - traw)
                        if site + 5 + rel in (ENQUEUE, 0x140953770,
                                              0x1402202C0, 0x140953800):
                            kind = {ENQUEUE: "ENQUEUE",
                                    0x140953770: "BATCH",
                                    0x1402202C0: "ARRAY24",
                                    0x140953800: "BATCH"}[site + 5 + rel]
                        break
            kinds.append("%s@%X" % (kind, v))
        print("%-42s 0x%08X  %s" % (nm, h, " ".join(kinds) if kinds else "-"))


if __name__ == "__main__":
    main(sys.argv[1:])
