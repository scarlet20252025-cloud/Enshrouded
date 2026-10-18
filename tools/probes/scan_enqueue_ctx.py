"""For every `call Enqueue` site, work out how RCX (the world ctx) was loaded.

This is the fastest way to find a *global* world-admin pointer: if any caller
loads rcx from a RIP-relative slot, that slot is the world/entity admin and we
can read it directly instead of waiting for a component write to happen.

Reports, per call site:
  - the preceding 40 bytes disassembled-by-hand summary (raw hex)
  - any `48 8B 0D <disp32>` (mov rcx, [rip+disp]) found within 40 bytes before
    -> resolved absolute RVA of the named slot
  - any `48 8B 4C 24 xx` (mov rcx,[rsp+xx]) / `48 8B 4D xx` (mov rcx,[rbp+xx])
  - any `48 89 C1` (mov rcx, rax) etc.

Usage: python tools/scan_enqueue_ctx.py
"""
import json
import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXE = Path(r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe")

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


def sec_of(secs, rva):
    for name, vaddr, vsize, rawptr, rawsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rawsize):
            return name
    return "?"


def main():
    data = EXE.read_bytes()
    secs = sections(data)
    text = next(s for s in secs if s[0] == ".text")
    _, tva, tvsize, traw, trawsize = text
    tstart = 0x1000
    tend = tstart + trawsize

    def off(rva):
        return traw + (rva - tva)

    # --- 1. every 8-byte absolute reference to Enqueue anywhere in the file ---
    target_va = 0x140000000 + ENQUEUE_RVA
    needle = struct.pack("<Q", target_va)
    abshit = []
    p = 0
    while True:
        p = data.find(needle, p)
        if p < 0:
            break
        abshit.append(p)
        p += 1
    print(f"absolute 8-byte references to Enqueue: {len(abshit)}")

    # --- 2. call sites ---
    calls = []
    rva = tstart
    while rva < tend - 5:
        o = off(rva)
        if data[o] == 0xE8:
            rel, = struct.unpack_from("<i", data, o + 1)
            if rva + 5 + rel == ENQUEUE_RVA:
                calls.append(rva)
        rva += 1
    print(f"relative call sites: {len(calls)}\n")

    globals_found = Counter()
    forms = Counter()

    for c in calls:
        # scan back up to 40 bytes for the last write to rcx
        best = None
        for back in range(1, 41):
            s = c - back
            if s < tstart:
                break
            o = off(s)
            # 48 8B 0D disp32  -> mov rcx, [rip+disp32]
            if data[o] == 0x48 and data[o + 1] == 0x8B and data[o + 2] == 0x0D:
                d, = struct.unpack_from("<i", data, o + 3)
                slot = s + 7 + d
                globals_found[slot] += 1
                best = ("global", slot, s)
                break
            # 48 8B 4C 24 xx -> mov rcx,[rsp+xx]
            if data[o] == 0x48 and data[o + 1] == 0x8B and data[o + 2] == 0x4C:
                best = ("stack", data[o + 3], s)
                break
            # 48 8B 4D xx -> mov rcx,[rbp+xx]
            if data[o] == 0x48 and data[o + 1] == 0x8B and data[o + 2] == 0x4D:
                best = ("rbp", data[o + 3], s)
                break
            # 48 8B 4E xx / 4F / 4B ...  -> mov rcx,[rsi+xx] etc.
            if data[o] == 0x48 and data[o + 1] == 0x8B and data[o + 2] in (0x4E, 0x4F, 0x4B, 0x4A, 0x49, 0x48):
                best = ("regdisp", data[o + 2], s)
                break
            # 48 89 C1 -> mov rcx, rax ; 48 8B C8 -> mov rcx, rax
            if data[o] == 0x48 and data[o + 1] == 0x89 and (data[o + 2] & 0xF8) == 0xC0:
                src = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"][data[o + 2] & 7]
                best = ("mov", src, s)
                break
            if data[o] == 0x48 and data[o + 1] == 0x8B and (data[o + 2] & 0xC7) == 0xC1:
                src = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"][(data[o + 2] >> 3) & 7]
                best = ("mov", src, s)
                break
        if best:
            forms[best[0]] += 1

    print("how rcx was derived (nearest preceding write):")
    for k, v in forms.most_common():
        print(f"   {k:<10} {v}")

    print("\nglobals loaded into rcx before `call Enqueue`:")
    for slot, n in globals_found.most_common():
        print(f"   rva 0x{slot:X} [{sec_of(secs, slot)}]  x{n}")

    if not globals_found:
        print("   (none)")


if __name__ == "__main__":
    main()
