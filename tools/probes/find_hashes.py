"""Find every occurrence of a set of type hashes in the exe and classify context.

For each hash, report file offset / RVA / section and, for .text hits, the
16 bytes before (so we can see whether a `mov [reg+0xC], imm32` is being done).

Usage: python tools/find_hashes.py <name>[,<name>...]   (or no args = builtin set)
"""
import fnmatch
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe")
REFL = ROOT / "tools" / "kfc" / "reflection_data.json"

WANT = [
    "keen::ecs::PlayerInput",
    "keen::ecs::ClientPlayerInput",
    "keen::ecs::AdminSpawnCommand",
    "keen::ecs::AdminDebugEnemyAction",
    "keen::ecs::IsTame",
    "keen::ecs::CurrentTransform",
    "keen::ecs::PlayerFocus",
    "keen::ecs::ClientPlayerFocus",
    "keen::ecs::Faction",
    "keen::ecs::Health",
    "keen::actor::TameWildlifeEvent",
    "keen::actor::SpawnEntityEvent",
]


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


def classify(secs, off):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if rawptr <= off < rawptr + rawsize:
            return name, vaddr + (off - rawptr)
    return "?", -1


def main():
    data = EXE.read_bytes()
    secs = sections(data)
    hashes = json.load(open(REFL, "r", encoding="utf-8"))
    types = hashes["types"] if isinstance(hashes, dict) and "types" in hashes else hashes
    byname = {(t.get("qualifiedName") or t.get("name")): t for t in types}

    wants = WANT
    if len(sys.argv) > 1:
        wants = sys.argv[1].split(",")

    for w in wants:
        t = byname.get(w)
        if not t:
            print(f"{w}: NOT IN REFLECTION")
            continue
        qh = t["qualifiedHash"] & 0xFFFFFFFF
        needle = struct.pack("<I", qh)
        hits = []
        start = 0
        while True:
            p = data.find(needle, start)
            if p < 0:
                break
            hits.append(p)
            start = p + 1
        print(f"\n### {w}  qh=0x{qh:08X}  size={t.get('size')}  hits={len(hits)}")
        for p in hits[:20]:
            sec, rva = classify(secs, p)
            prev = data[max(0, p - 12):p]
            nxt = data[p + 4:p + 12]
            ctx = prev.hex(" ")
            print(f"   file 0x{p:X}  rva 0x{rva:X} [{sec}]  prev: {ctx}")

    # Also: is a plain immediate store of the hash findable? Search for the
    # 3-byte pattern C7 4x 0C followed by any hash we know.
    print("\n=== `mov [reg+0xC], imm32` stores in .text ===")
    text = next(s for s in secs if s[0] == ".text")
    _, tva, tvsize, traw, trawsize = text
    hits = 0
    for i in range(traw, traw + trawsize - 7):
        if data[i] != 0xC7:
            continue
        m = data[i + 1]
        if (m & 0xC7) != 0x40:      # mod=01, rm=reg
            continue
        if data[i + 2] != 0x0C:
            continue
        imm, = struct.unpack_from("<I", data[i + 3])
        if imm in HASH_SET:
            continue
    print("   (see scan_comp_writers.py for the resolved map)")


HASH_SET = set()

if __name__ == "__main__":
    main()
