# -*- coding: utf-8 -*-
"""
Verify + dump the reflection table properly.

TypeMetadata (0x90 bytes) at each VA in the array at file 0x16FC350:
  +0x00 name_ptr(u64)          +0x08 name_len(u64)
  +0x10 impact_name_ptr        +0x18 impact_name_len
  +0x20 qualified_name_ptr     +0x28 qualified_name_len
  +0x30 namespace_ptr          +0x38 inner_type_ptr
  +0x40 size(u32) +0x44 alignment(u16) +0x46 element_alignment(u16)
  +0x48 field_count(u32)
  +0x4C primitive_type(u8) +0x4D flags(u8)
  +0x50 qualified_hash(u32) +0x54 internal_hash(u32)
  +0x58 struct_fields_ptr(u64) +0x60 enum_fields_ptr(u64) +0x68 variant_type_ptr
  +0x70 default_value_ptr +0x78 default_value_len
  +0x80 attributes_ptr +0x88 attributes_count

StructFieldMetadata stride 0x30:
  +0x00 name_ptr(u64) +0x08 name_len(u64) +0x10 type_ptr(u64 VA)
  +0x18 data_offset(u64) +0x20 attributes_ptr +0x28 attributes_count
"""
import struct, json, sys, os

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IMG = 0x140000000
ARRAY_FO = 0x16FC350
COUNT = 12646

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

DATA, SECS = sections()

def rva2fo(rva):
    for nm, va, vsize, raw, rawsize in SECS:
        if va <= rva < va + max(vsize, rawsize):
            return raw + (rva - va)
    return None

def rdva(va, n):
    if va < IMG:
        return b''
    fo = rva2fo(va - IMG)
    if fo is None:
        return b''
    return DATA[fo:fo+n]

def cstr(va, maxlen=512):
    b = rdva(va, maxlen)
    z = b.find(b'\0')
    if z >= 0:
        b = b[:z]
    return b.decode('latin1')

def read_meta(idx, ptrs):
    va = ptrs[idx]
    rec = rdva(va, 0x90)
    if len(rec) < 0x90:
        return None
    # NOTE: 2 bytes of padding at +0x4E (after ptype/flags) before qualified_hash@0x50.
    # '<' means no auto-alignment, so the pad must be explicit ('2x').
    (np_, nl, ip_, il, qp_, ql, nsp, itp,
     size, align, ealign, fcount, ptype, flags, qh, ih,
     sfp, efp, vtp, dvp, dvl, atp, atc) = struct.unpack_from(
        '<QQQQQQQQ I H H I B B 2x I I Q Q Q Q Q Q Q'.replace(' ', ''), rec, 0)
    return dict(idx=idx, va=va, size=size, align=align, ealign=ealign,
                field_count=fcount, ptype=ptype, flags=flags, qh=qh, ih=ih,
                struct_fields_ptr=sfp, enum_fields_ptr=efp,
                name=cstr(np_) if np_ else '',
                qualified=cstr(qp_) if qp_ else '',
                impact=cstr(ip_) if ip_ else '')

def read_fields(meta):
    out = {}
    if not meta or not meta['struct_fields_ptr'] or not meta['field_count']:
        return out
    n = meta['field_count']
    raw = rdva(meta['struct_fields_ptr'], 0x30 * n)
    if len(raw) < 0x30 * n:
        return out
    for i in range(n):
        (np_, nl, tp, doff, atp, atc) = struct.unpack_from('<QQQQQQ', raw, i*0x30)
        out[cstr(np_)] = dict(name=cstr(np_), type_va=tp, data_offset=doff,
                              attributes=atc)
    return out

def main():
    ptrs = struct.unpack_from('<%dQ' % COUNT, DATA, ARRAY_FO)
    what = sys.argv[1] if len(sys.argv) > 1 else 'landmarks'

    if what == 'landmarks':
        for idx in (0, 127, 136, 208, 732, 881, 989, 1900, 2887, 2898, 3298, 3635):
            m = read_meta(idx, ptrs)
            if not m:
                print('idx %d: unreadable' % idx)
                continue
            print('idx %-6d size=%-6d align=%-3d fields=%-4d pt=0x%02X qh=0x%08X  %s'
                  % (idx, m['size'], m['align'], m['field_count'], m['ptype'],
                     m['qh'], m['qualified']))
        print()
        for idx in (989, 2887, 2898, 1900, 3298, 3635, 881, 732, 208):
            m = read_meta(idx, ptrs)
            print('--- %s (idx %d, size %d) ---' % (m['qualified'], idx, m['size']))
            for fname, f in sorted(read_fields(m).items(), key=lambda kv: kv[1]['data_offset']):
                # resolve type index of the field
                ti = None
                for j, p in enumerate(ptrs):
                    if p == f['type_va']:
                        ti = j
                        break
                tn = ''
                if ti is not None:
                    tm = read_meta(ti, ptrs)
                    tn = tm['qualified'] if tm else '?'
                print('   +%-5d %-28s -> idx %-6s %s' %
                      (f['data_offset'], fname, ti, tn))
            print()
    elif what == 'dump':
        # dump all types to json (like reflection_data.json)
        out = []
        for idx in range(COUNT):
            m = read_meta(idx, ptrs)
            if not m:
                continue
            f = read_fields(m)
            m['structFields'] = {k: dict(name=v['name'],
                                         type=None,
                                         dataOffset=v['data_offset'])
                                 for k, v in f.items()}
            out.append(m)
        dst = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           'live_types.json')
        with open(dst, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, ensure_ascii=False)
        print('wrote %d types -> %s' % (len(out), dst))

if __name__ == '__main__':
    main()
