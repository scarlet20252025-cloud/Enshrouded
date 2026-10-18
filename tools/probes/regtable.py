# -*- coding: utf-8 -*-
"""
Enumerate the type-hash registry table in .rdata and dump the entries for
the hashes we care about.  Structure observed at rva 0x174B210:

    0x174B210:  a2 fc db 06   <- qualifiedHash (AdminSpawnCommand)
               8a 4d 09 7e   <- internalHash
               d0 99 74 41 01 00 00 00   <- VA of a "level1" descriptor
               (then zeros)

and at 0x17499D0:
               c0 41 50 41 01 00 00 00   <- VA 0x141503D80 (field-name pool)
               0b 00 00 00 ...           <- count/len
So each entry seems to be:
   {u32 qualifiedHash, u32 internalHash, u64 level1Ptr, ...}

The table is sorted by qualifiedHash.  Let's find the table bounds and
dump every entry, resolving level1Ptr to a readable string so we can name
each entry.  Then we can search for the entries of our target hashes and
learn the exact field order.
"""
import struct, sys

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IMG = 0x140000000

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

def rva2file(rva):
    for nm, va, vsize, raw, rawsize in SECS:
        if va <= rva < va + max(vsize, rawsize):
            return raw + (rva - va)
    return None

SECS = []

def cstr_at_va(va, maxlen=128):
    fo = rva2file(va - IMG)
    if fo is None:
        return None
    b = DATA[fo:fo+maxlen]
    z = b.find(b'\0')
    if z >= 0:
        b = b[:z]
    return b.decode('latin1')

def read_at_va(va, n):
    fo = rva2file(va - IMG)
    if fo is None:
        return b''
    return DATA[fo:fo+n]

DATA = None

def main():
    global DATA, SECS
    DATA, SECS = sections()
    # find table start: entry for AdminSpawnCommand at rva 0x174B210
    # walk backwards while entries look like {u32 hash, u32 hash, u64 ptr}
    target = int(sys.argv[1], 0) if len(sys.argv) > 1 else 0x174B210
    fo = rva2file(target)
    print('entry file offset 0x%X' % fo)
    # dump 0x200 bytes before and after
    b = DATA[fo-0x100:fo+0x100]
    for i in range(0, len(b), 16):
        row = b[i:i+16]
        addr = fo - 0x100 + i
        h = ' '.join('%02x' % c for c in row)
        a = ''.join(chr(c) if 32 <= c < 127 else '.' for c in row)
        print('%08x  %-47s  %s' % (addr, h, a))
    # try to interpret entries: assume 0x18-byte stride
    print('\n--- interpreting as 0x18-stride entries ---')
    start = fo - 0x100
    for i in range(start, fo + 0x100, 0x18):
        if i + 0x18 > len(DATA):
            break
        qh, ih, p = struct.unpack_from('<IIQ', DATA, i)
        # the u64 is really u64 ptr + maybe u32 more; try 0x18 stride with
        # {u32,u32,u64,u32}
        v = struct.unpack_from('<IIQI', DATA, i)
        s = cstr_at_va(v[2]) if v[2] > IMG else ''
        s = ''.join(ch if 32 <= ord(ch) < 127 else '.' for ch in (s or '?'))
        print('%08x: qh=%08X ih=%08X ptr=0x%X (%s) tail=%d' %
              (i, v[0], v[1], v[2], s[:40], v[3]))

if __name__ == '__main__':
    main()
