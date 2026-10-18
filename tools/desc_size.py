r"""Measure the REAL size of a descriptor by walking its group list, so we know
how much memory a synthesized descriptor needs.

Layout (MODLOG 1161-1193):
  +0x00 char* name
  +0x08 u64  nameLen
  +0x10 void* handler
  +0x18 ... groups of {char** pool; u32 count; u32 pad}
  +0x180 u32 (copied to slot+0x20)
  +0x184 u32 (copied to slot+0x24)

The list ends at the first pair where BOTH this and the next group are {0,0}.

Print, for each of the 16 descriptors: base, name, handler, group list, and the
offset of the terminator (=> minimal descriptor size).
"""
import struct

sys_path = r"E:\DSH\肥鱼乐园\WolfMount\tools"
import sys
sys.path.insert(0, sys_path)
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE
THUNKS = [0x12CF5C0 + 0x10 * i for i in range(16)]


def read_desc(data, secs, desc_va):
    rva = desc_va - IB
    off = S.va_to_off(secs, desc_va)
    name_ptr, name_len, handler = struct.unpack_from("<QQQ", data, off)
    groups = []
    o = off + 0x18
    i = 0
    while True:
        pool, count, pad = struct.unpack_from("<QII", data, o)
        groups.append((pool, count))
        nxt_pool, nxt_count, nxt_pad = struct.unpack_from("<QII", data, o + 0x10)
        if pool == 0 and count == 0 and nxt_pool == 0 and nxt_count == 0:
            break
        o += 0x10
        i += 1
        if i > 40:
            break
    return name_ptr, name_len, handler, groups, (o + 0x10) - off


def main():
    data = S.load()
    secs = S.sections(data)

    # resolve the lea thunks to get descriptor addresses
    print("%-34s %-10s %-10s %-6s %s" % ("name", "desc_rva", "handler_rva", "groups", "term_off"))
    for t in THUNKS:
        va = IB + t
        off = S.va_to_off(secs, va)
        # lea rax,[rip+d]; ret  -> 48 8d 05 dd dd dd dd c3
        if data[off:off + 3] != b"\x48\x8d\x05":
            print("thunk %#x is not lea/ret: %s" % (t, data[off:off + 8].hex()))
            continue
        rel = struct.unpack_from("<i", data, off + 3)[0]
        desc_va = va + 7 + rel
        np_, nl, h, groups, term = read_desc(data, secs, desc_va)
        # read the name
        no = S.va_to_off(secs, np_)
        nm = data[no:no + 40].split(b"\0")[0].decode("latin1")
        print("%-34s %-10s %-10s %-6d %s  groups=%s" % (
            nm, hex(desc_va - IB), hex(h - IB), len(groups), hex(term),
            [(hex(p - IB), c) for p, c in groups]))


if __name__ == "__main__":
    main()
