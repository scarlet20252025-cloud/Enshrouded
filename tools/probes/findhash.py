# -*- coding: utf-8 -*-
"""
Find the runtime dispatcher for a reflected type by scanning .text for
`movl $<qualifiedHash>, %edx` followed closely by `movl $<size>, %r8d` and a
`call`.

Pattern for AdminSpawnCommand (hash 0x06DBFCA2, size 80):
    BA A2 FC DB 06        movl $0x6dbfca2, %edx
    41 B8 50 00 00 00     movl $0x50, %r8d
    ...                   (movq %rax,%rcx etc, up to 5 instrs)
    E8 xx xx xx xx        call

We only know the AdminSpawnCommand hash appears once in .rdata (registry).
If a code site exists we must find it.  Let's search for the hash literal
in .text specifically, then for the "movl $imm32, %edx" encoding of it.

Also search for TameWildlifeEvent (0x537B675C) and EntityDiedEvent
(0xD8EC982A) to see the shape of the event dispatch table.
"""
import struct, sys

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

def sections():
    with open(EXE, 'rb') as f:
        data = f.read()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    optsz = struct.unpack_from('<H', data, pe + 20)[0]
    off = pe + 24 + optsz
    secs = []
    for i in range(nsec):
        nm = data[off:off+8].rstrip(b'\0').decode('latin1')
        vsize, va, rawsize, raw = struct.unpack_from('<IIII', data, off+8)
        secs.append((nm, va, vsize, raw, rawsize))
        off += 40
    return data, secs

def main():
    hashes = {
        'AdminSpawnCommand': 0x06DBFCA2,
        'AdminDebugEnemyAction': 0x14CC3955,
        'TameWildlifeEvent': 0x537B675C,
        'EntityDiedEvent': 0xD8EC982A,
        'HitEvent': 0xCC0D57E0,
    }
    data, secs = sections()
    for name, h in hashes.items():
        pat = struct.pack('<I', h)
        print('=== %s (0x%08X) ===' % (name, h))
        start = 0
        n = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            start = i + 1
            n += 1
            sec = None
            rva = None
            for sn, va, vsize, raw, rawsize in secs:
                if raw <= i < raw + rawsize:
                    sec = sn
                    rva = va + (i - raw)
            print('  file 0x%X rva 0x%X [%s]' % (i, rva or 0, sec or '?'))
            if n > 40:
                print('  ... (truncated)')
                break
        if n == 0:
            print('  (none)')

if __name__ == '__main__':
    main()
