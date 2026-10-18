r"""Decode the 8-byte lea-ret thunks at 0x12cf5c0 and the table they point at.

Each thunk is `lea rax, [rip+d] ; ret`, i.e. a getter for a static descriptor.
The d values resolve to the .rdata records we found. This is the behaviour
registry accessor table.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def main():
    data = S.load()
    secs = S.sections(data)
    tsec = next(s for s in secs if s["name"] == ".text")
    start = 0x12CF5C0
    end = 0x12CF6C0
    off = tsec["raw"] + (start - tsec["va"])
    limit = tsec["raw"] + min(tsec["rawsize"], end - tsec["va"])
    print("thunk table at rva=%#x (file %#x):" % (start, off))
    n = 0
    while off + 16 <= limit:
        b = data[off:off + 8]
        if b[0] == 0x48 and b[1] == 0x8D and b[2] == 0x05 and b[7] == 0xC3:
            rel = struct.unpack_from("<i", b, 3)[0]
            insn_va = S.IMAGE_BASE + start + n * 16
            tgt = insn_va + 7 + rel
            print("  thunk rva=%#x -> %#x" % (start + n * 16, tgt - S.IMAGE_BASE))
            n += 1
        off += 16
    print("total thunks: %d" % n)


if __name__ == "__main__":
    main()
