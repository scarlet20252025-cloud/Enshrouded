#!/usr/bin/env python3
"""Section-correct reference scanner for enshrouded.exe.

The old ad-hoc scans mixed up .rdata and .pdata raw offsets, which produced
garbage results. This module derives the section table from the PE itself so
every va<->file mapping is provably correct.

Usage:
    python tools/scanrefs.py <hexhash> [<hexhash> ...]
    python tools/scanrefs.py --type keen::ecs::IsTame
"""
import struct
import sys

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IMAGE_BASE = 0x140000000


def load():
    with open(EXE, "rb") as f:
        return f.read()


def sections(data):
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[pe:pe + 4] == b"PE\0\0", "not a PE"
    nsec = struct.unpack_from("<H", data, pe + 6)[0]
    opt = pe + 24
    optsz = struct.unpack_from("<H", data, pe + 20)[0]
    sec = pe + 24 + optsz
    out = []
    for i in range(nsec):
        off = sec + i * 40
        name = data[off:off + 8].rstrip(b"\0").decode("ascii", "replace")
        vsize, va, rawsize, raw = struct.unpack_from("<IIII", data, off + 8)
        out.append({"name": name, "va": va, "vsize": vsize,
                    "raw": raw, "rawsize": rawsize})
    return out


def va_to_off(secs, va):
    if va >= IMAGE_BASE:
        va -= IMAGE_BASE
    for s in secs:
        if s["va"] <= va < s["va"] + max(s["vsize"], s["rawsize"]):
            d = va - s["va"]
            if d < s["rawsize"]:
                return s["raw"] + d
    return None


def off_to_va(secs, off):
    for s in secs:
        if s["raw"] <= off < s["raw"] + s["rawsize"]:
            return IMAGE_BASE + s["va"] + (off - s["raw"])
    return None


def text_span(secs):
    for s in secs:
        if s["name"] == ".text":
            return s["raw"], s["raw"] + s["rawsize"]
    raise SystemExit("no .text")


def find_dword(data, secs, value, only=None):
    pat = struct.pack("<I", value)
    hits = []
    for s in secs:
        if only and s["name"] not in only:
            continue
        lo, hi = s["raw"], s["raw"] + s["rawsize"]
        i = lo
        while True:
            i = data.find(pat, i, hi)
            if i < 0:
                break
            hits.append((s["name"], IMAGE_BASE + s["va"] + (i - s["raw"])))
            i += 1
    return hits


def callers(data, secs, target):
    lo, hi = text_span(secs)
    tlo = None
    for s in secs:
        if s["name"] == ".text":
            tlo = IMAGE_BASE + s["va"]
    hits = []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == target:
                hits.append(insn)
    return hits


def pdata_funcs(data, secs):
    for s in secs:
        if s["name"] == ".pdata":
            out = []
            for k in range(s["raw"], s["raw"] + s["rawsize"], 12):
                b, e, u = struct.unpack_from("<III", data, k)
                if b:
                    out.append((IMAGE_BASE + b, IMAGE_BASE + e))
            return out
    return []


def enclosing(funcs, va):
    for b, e in funcs:
        if b <= va < e:
            return b, e
    return None


def main():
    data = load()
    secs = sections(data)
    if "--sections" in sys.argv or len(sys.argv) == 1:
        for s in secs:
            print("%-10s va=%08x vsize=%08x raw=%08x rawsize=%08x"
                  % (s["name"], s["va"], s["vsize"], s["raw"], s["rawsize"]))
        return

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    values = []
    if "--type" in sys.argv:
        name = args[0]
        sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
        import json
        d = json.load(open(r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json",
                           encoding="utf-8"))
        for t in d["types"]:
            if t.get("qualifiedName") == name:
                values.append((name, t["qualifiedHash"]))
    else:
        for a in args:
            values.append((a, int(a, 16)))

    funcs = pdata_funcs(data, secs)
    for label, h in values:
        print("== %s  0x%08X" % (label, h))
        hits = find_dword(data, secs, h)
        if not hits:
            print("   no references anywhere")
            continue
        for sec, va in hits:
            if sec == ".text":
                r = enclosing(funcs, va)
                fn = "func 0x%X (size %d)" % (r[0], r[1] - r[0]) if r else "no .pdata func"
                ctx = data[va_to_off(secs, va) - 8:va_to_off(secs, va) + 4]
                print("   .text 0x%X  %s  ctx=%s" % (va, fn, ctx.hex()))
            else:
                print("   %s 0x%X" % (sec, va))


if __name__ == "__main__":
    main()
