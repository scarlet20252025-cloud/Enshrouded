r"""Find the behaviour-registry registration call that consumes 0x141e2b670.

The record at 0x141e2b670 ends with FN 0x480a70 (the "wildlife" behaviour) and
is preceded by a string table. Find code that references 0x141e2b670 or the
record start, to learn the registration function we can call to install a custom
behaviour.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

TARGETS = [0x141E2B670, 0x141E2B640, 0x141E2B4A0, 0x141E2B560, 0x141E2B590]


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    for tva in TARGETS:
        t = S.IMAGE_BASE + tva
        # u64 refs
        pat = struct.pack("<Q", t)
        for sec in secs:
            i = sec["raw"]
            hi = sec["raw"] + sec["rawsize"]
            while True:
                i = data.find(pat, i, hi)
                if i < 0:
                    break
                print("u64 ref %#x in %s rva=%#x" % (tva, sec["name"],
                                                     S.IMAGE_BASE + sec["va"] + (i - sec["raw"])))
                i += 1
        # lea rip
        lo, hi = S.text_span(secs)
        tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")
        for i in range(lo, hi - 7):
            if data[i] == 0x48 and data[i + 1] == 0x8D and (data[i + 2] & 0xC7) == 0x05:
                rel = struct.unpack_from("<i", data, i + 3)[0]
                insn = tlo + (i - lo)
                if insn + 7 + rel == t:
                    r = S.enclosing(funcs, insn)
                    print("lea to %#x at rva=%#x  %s" % (
                        tva, insn - S.IMAGE_BASE,
                        ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))
            elif data[i] in (0xE8, 0xE9):
                rel = struct.unpack_from("<i", data, i + 1)[0]
                insn = tlo + (i - lo)
                if insn + 5 + rel == t:
                    r = S.enclosing(funcs, insn)
                    print("call/jmp to %#x at rva=%#x  %s" % (
                        tva, insn - S.IMAGE_BASE,
                        ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
