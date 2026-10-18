"""Map the two component-writer families in .text.

Family A (Enqueue-return pattern, used by SetIsTame):
    call Enqueue
    mov [rax+0xC], <typeHash>      ; C7 40 0C imm32
    ...

Family B (direct-payload pattern, seen around cast/attach code):
    call X
    mov [rax], <typeHash>          ; C7 00 imm32
    mov [rax+4], ...               ; value follows immediately at payload+4

For every store of a known type hash we report the site, the store form, and
the nearest preceding `call` (plus its resolved target), so the helper each
family funnels through becomes visible.

Usage: python tools/scan_hash_stores.py [--all]
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe")
REFL = ROOT / "tools" / "kfc" / "reflection_data.json"

ENQUEUE_RVA = 0x952400


def sections(data):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e_lfanew + 4
    nsec, = struct.unpack_from("<H", data, coff + 2)
    optsize, = struct.unpack_from("<H", data, coff + 16)
    opt = coff + 20
    out = []
    for i in range(nsec):
        o = opt + optsize + i * 40
        name = data[o:o + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        out.append((name, vaddr, vsize, rawptr, rawsize))
    return out


def load_hashes():
    d = json.load(open(REFL, "r", encoding="utf-8"))
    types = d["types"] if isinstance(d, dict) and "types" in d else d
    m = {}
    for t in types:
        qh = t.get("qualifiedHash")
        if qh is None:
            continue
        m[qh & 0xFFFFFFFF] = t.get("qualifiedName") or t.get("name")
    return m


def main():
    data = EXE.read_bytes()
    secs = sections(data)
    hashes = load_hashes()

    text = next(s for s in secs if s[0] == ".text")
    _, tva, tvsize, traw, trawsize = text
    tstart = 0x1000
    tend = tstart + trawsize

    def off_of(rva):
        return traw + (rva - tva)

    def near_call(rva_site):
        """Nearest preceding E8 call within 20 bytes."""
        for back in range(2, 22):
            p = rva_site - back
            if p < tstart:
                break
            o = off_of(p)
            if data[o] != 0xE8:
                continue
            rel, = struct.unpack_from("<i", data, o + 1)
            tgt = p + 5 + rel
            # only accept if the call *ends* at or before the store
            if p + 5 <= rva_site:
                return p, tgt
        return None, None

    famA = {}   # hash -> [(site, enqcall, type)]
    famB = {}
    other = {}

    rva = tstart
    while rva < tend - 8:
        o = off_of(rva)
        if data[o] != 0xC7:
            rva += 1
            continue
        modrm = data[o + 1]
        kind = None
        imm = None
        if modrm == 0x00:                       # mov dword [rax], imm32
            imm, = struct.unpack_from("<I", data, o + 2)
            kind = "B"
        elif (modrm & 0xC7) == 0x40 and data[o + 2] == 0x0C:
            imm, = struct.unpack_from("<I", data, o + 3)
            kind = "A"
        if kind is None:
            rva += 1
            continue
        name = hashes.get(imm)
        if name is None:
            rva += 1
            continue
        csite, ctgt = near_call(rva)
        rec = (rva, csite, ctgt)
        if kind == "A" and ctgt == ENQUEUE_RVA:
            famA.setdefault(name, []).append(rec)
        elif kind == "B":
            famB.setdefault(name, []).append(rec)
        else:
            other.setdefault(name, []).append((rec, kind, ctgt))
        rva += 1
        continue

    def report(title, table, show_target=True):
        print("=" * 74)
        print(title, f"({len(table)} types)")
        print("=" * 74)
        for name in sorted(table):
            rows = table[name]
            tgts = sorted({r[2] for r in rows if r[2] is not None})
            tgt_txt = " ".join(f"0x{t:X}" for t in tgts[:4]) or "-"
            sites = ", ".join(f"0x{r[0]:X}" for r in rows[:6])
            more = "" if len(rows) <= 6 else f" (+{len(rows)-6})"
            print(f"  {name:<50} x{len(rows):<3} helper={tgt_txt}")
            print(f"      sites: {sites}{more}")
        print()

    report("FAMILY A — `call Enqueue; mov [rax+0xC], hash`", famA)
    report("FAMILY B — `call X; mov [rax], hash`  (payload at rax)", famB)

    if other:
        print("=" * 74)
        print("OTHER — `mov [rax+0xC], hash` not preceded by Enqueue")
        print("=" * 74)
        for name in sorted(other):
            rows = other[name]
            for (site, csite, ctgt), kind, _ in rows[:8]:
                print(f"  {name:<50} site=0x{site:X} call=0x{csite:X} -> 0x{ctgt:X}")


if __name__ == "__main__":
    main()
