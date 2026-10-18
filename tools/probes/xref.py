# -*- coding: utf-8 -*-
"""
Scan the enshrouded.exe .text for code that references a given RVA via
RIP-relative addressing.  The compiler emits:

    lea reg, [rip+disp32]          48 8D <modrm=00rrr101> <disp32>
    mov reg, [rip+disp32]          48 8B <modrm=00rrr101> <disp32>
    cmp reg, [rip+disp32]          48 3B / 48 39 ...
    mov [rip+disp32], reg          48 89 <modrm=00rrr101> <disp32>

For a target RVA T and an instruction at file offset F (RVA R), the
displacement satisfies: T = R_next + disp, i.e.
    disp = T - (R + insnLen)

So instead of decoding, we scan every 4-byte little-endian value D at
offset O in .text, compute candidate instruction start I = O - 4 - k
(k = length of the opcode prefix before the disp32), and check whether
I + 4 + D == T.  We accept k in {0,1,2,3} and require the byte at O-4-k
to be a plausible opcode prefix (48/4C REX, or 8D/8B/89/39/3B/0FB6...).

This finds RIP-relative xrefs without a full disassembler.
"""
import struct, sys, os

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

REX = {0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F}
OPCODES = {0x8D, 0x8B, 0x89, 0x39, 0x3B, 0x63, 0x8A, 0x88, 0x85, 0x84,
           0xC7, 0x83, 0x81, 0x03, 0x2B, 0x09, 0x0B, 0x21, 0x23, 0x29,
           0x0F}

def find_xrefs(target_rva, secs, data, restrict_text=True):
    """Return list of (file_off_of_disp32, insn_rva, opcode_prefix_len)."""
    hits = []
    for nm, va, vsize, raw, rawsize in secs:
        if restrict_text and nm != '.text':
            continue
        base = raw
        end = raw + rawsize
        # scan for the 4-byte displacement whose computed target matches
        i = base
        # quick prefilter: disp32 = target - (insn_rva + 4). insn_rva in .text
        # is within [va, va+rawsize). So disp in [target-va-rawsize-8, target-va-4]
        dlo = target_rva - (va + rawsize + 16)
        dhi = target_rva - va + 16
        while i < end - 4:
            # cheap byte scan using struct at each position is slow in python;
            # use a windowed find on the low byte first
            pass
        # do a straightforward scan but with numpy-free optimisation:
        # find candidate positions by searching for 4-byte patterns is not
        # possible (unknown).  Instead iterate in chunks and use int.from_bytes
        off = base
        CH = 1 << 20
        while off < end:
            chunk = data[off:min(off+CH, end)]
            for j in range(0, len(chunk) - 4):
                d = struct.unpack_from('<i', chunk, j)[0]
                if d < dlo or d > dhi:
                    continue
                pos = off + j
                # candidate disp32 ends at pos+4; instruction RVA = file2rva(pos+4)
                rva_next = va + (pos + 4 - raw)
                if rva_next + d == target_rva:
                    # validate opcode prefix before the disp32
                    for k in (2, 1, 0, 3):
                        p = pos - 4 - k
                        if p < raw:
                            continue
                        b = data[p]
                        if b in REX or b in OPCODES:
                            hits.append((pos, va + (p - raw), k))
                            break
            off += CH
    return hits

def main():
    t = int(sys.argv[1], 0)
    data, secs = sections()
    hits = find_xrefs(t, secs, data)
    print('=== %d xref(s) to rva 0x%X ===' % (len(hits), t))
    seen = set()
    for pos, insn_rva, k in sorted(hits, key=lambda h: h[1]):
        key = insn_rva
        if key in seen:
            continue
        seen.add(key)
        # dump 16 bytes of context around the instruction
        s = max(0, insn_rva - 8)
        foff = None
        for nm, va, vsize, raw, rawsize in secs:
            if va <= s < va + rawsize:
                foff = raw + (s - va)
        ctx = data[foff:foff+32] if foff else b''
        print('rva 0x%X  (disp32@file 0x%X, prefix %d)  ctx: %s' %
              (insn_rva, pos, k, ' '.join('%02x' % c for c in ctx)))

if __name__ == '__main__':
    main()
