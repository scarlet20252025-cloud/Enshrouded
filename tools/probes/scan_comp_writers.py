"""Map every component-write site: which type hash each `Enqueue` call writes.

SetIsTame showed the pattern:

    call Enqueue                 ; returns record in rax
    movl $<typeHash>, 0xC(%rax)  ; payload[0] = component type hash

So for each `E8 rel32` call whose target is Enqueue (rva 0x952400) we scan the
following bytes for `C7 <modrm with disp8 0x0C> <imm32>` and resolve imm32
through the reflection table.  Target register may be rax/rbx/rcx/rdx/rsi/rdi.

Usage:  python tools/scan_comp_writers.py [--window N]
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe")
REFL = ROOT / "tools" / "kfc" / "reflection_data.json"

IMAGE_BASE = 0x140000000
ENQUEUE_RVA = 0x952400

sys.path.insert(0, str(ROOT / "tools"))


def load_sections(data):
    e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]
    coff = e_lfanew + 4
    nsec, = struct.unpack_from("<H", data, coff + 2)
    optsize, = struct.unpack_from("<H", data, coff + 16)
    opt = coff + 20
    secs = []
    for i in range(nsec):
        o = opt + optsize + i * 40
        name = data[o:o + 8].rstrip(b"\0").decode("latin1")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, o + 8)
        secs.append((name, vaddr, vsize, rawptr, rawsize))
    return secs


def rva_to_off(secs, rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            d = rva - vaddr
            if d < rawsize:
                return rawptr + d
    return None


def off_to_rva(secs, off):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if rawptr <= off < rawptr + rawsize:
            return vaddr + (off - rawptr)
    return None


def load_hashes():
    d = json.load(open(REFL, "r", encoding="utf-8"))
    types = d["types"] if isinstance(d, dict) and "types" in d else d
    m = {}
    for t in types:
        qh = t.get("qualifiedHash")
        if qh is None:
            continue
        m[qh & 0xFFFFFFFF] = (t.get("qualifiedName") or t.get("name"),
                              t.get("size"))
    return m


def main():
    window = 160
    for i, a in enumerate(sys.argv):
        if a == "--window":
            window = int(sys.argv[i + 1])

    data = EXE.read_bytes()
    secs = load_sections(data)
    hashes = load_hashes()

    text = next(s for s in secs if s[0] == ".text")
    _, tva, tvsize, traw, trawsize = text
    tstart = 0x1000  # .text rva
    tend = tstart + trawsize
    print(f".text rva 0x{tstart:X}..0x{tend:X}  ({trawsize} bytes)")

    # 1) find all calls to Enqueue
    calls = []
    i = tstart
    while i < tend - 5:
        off = traw + (i - tva)
        if data[off] == 0xE8:
            rel, = struct.unpack_from("<i", data, off + 1)
            tgt = i + 5 + rel
            if tgt == ENQUEUE_RVA:
                calls.append(i)
        i += 1
    print(f"Enqueue call sites: {len(calls)}")

    # 2) for each, scan forward for `movl $imm32, 0xC(reg)`
    #    C7 /0 with modrm mod=01 (disp8) r/m=reg, disp = 0x0C
    MODRM_DISP8 = {0x40, 0x41, 0x42, 0x43, 0x46, 0x47}  # + 0x0C disp byte follows
    wanted = {}
    unmapped = {}
    for c in calls:
        start = c + 5
        end = min(start + window, tend)
        for p in range(start, end - 7):
            off = traw + (p - tva)
            if data[off] != 0xC7:
                continue
            modrm = data[off + 1]
            if modrm not in MODRM_DISP8:
                continue
            if data[off + 2] != 0x0C:
                continue
            imm, = struct.unpack_from("<I", data, off + 3)
            nm = hashes.get(imm)
            if nm is None:
                unmapped.setdefault(imm, []).append((c, p))
            else:
                wanted.setdefault(nm[0], []).append((c, imm, nm[1]))

    print(f"\nresolved component types written through Enqueue: {len(wanted)}")
    for name in sorted(wanted):
        sites = wanted[name]
        h = sites[0][1]
        sz = sites[0][2]
        site_txt = ", ".join(f"0x{c:X}" for c, _, _ in sites[:6])
        more = "" if len(sites) <= 6 else f" (+{len(sites)-6})"
        print(f"  {name:<52} qh=0x{h:08X} size={sz:<5} sites={len(sites):<3} {site_txt}{more}")

    if unmapped:
        print(f"\nunresolved imm32 values ({len(unmapped)}):")
        for imm, sites in sorted(unmapped.items()):
            print(f"  0x{imm:08X}  x{len(sites)}  first call 0x{sites[0][0]:X}")

    # 3) specifically: which site writes PlayerInput?
    print("\n--- PlayerInput (0xFB4F945A) write sites ---")
    hits = [(c, p) for c, p in
            [(c, p) for c in calls for p in range(c + 5, min(c + 5 + window, tend) - 7)
             if data[traw + (p - tva)] == 0xC7
             and data[traw + (p - tva) + 1] in MODRM_DISP8
             and data[traw + (p - tva) + 2] == 0x0C
             and struct.unpack_from("<I", data, traw + (p - tva) + 3)[0] == 0xFB4F945A]]
    if not hits:
        print("  none — PlayerInput is not written through an Enqueue call with this shape")
    for c, p in hits:
        print(f"  Enqueue call @0x{c:X}  hash store @0x{p:X}")


if __name__ == "__main__":
    main()
