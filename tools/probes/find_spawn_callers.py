r"""Find callers of the entity-spawn path.

The spawn component-pack builder at rva 0x2E134F constructs a 24-byte
descriptor list for a brand-new entity and then calls the ARRAY24 batch
submitter. Its callers are the real spawn entry points -- exactly what the
`spawn` console command needs. Uses scanrefs' PE-derived section table so the
va<->file mapping cannot be wrong.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def rel32_targets(data, secs, want):
    """All E8/E9 sites whose rel32 lands on `want` (a full VA)."""
    lo, hi = S.text_span(secs)
    tlo = None
    for s in secs:
        if s["name"] == ".text":
            tlo = S.IMAGE_BASE + s["va"]
    out = []
    for i in range(lo, hi - 5):
        if data[i] in (0xE8, 0xE9):
            rel = struct.unpack_from("<i", data, i + 1)[0]
            insn = tlo + (i - lo)
            if insn + 5 + rel == want:
                out.append(insn)
    return out


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)

    print("sections:")
    for s in secs:
        print("  %-10s va=%08x vsize=%08x raw=%08x rawsize=%08x"
              % (s["name"], s["va"], s["vsize"], s["raw"], s["rawsize"]))

    for rva, what in [
        (0x2E134F, "spawn component-pack builder"),
        (0x953800, "ARRAY24 batch submit"),
        (0x953770, "submit helper after the builder"),
        (0x2202C0, "ARRAY24 appender"),
        (0x21C390, "standalone Faction setter"),
        (0x47D040, "SetIsTame"),
        (0x9B0860, "GetCtx"),
    ]:
        want = S.IMAGE_BASE + rva
        callers = rel32_targets(data, secs, want)
        print("\n=== %s  rva=%#x  callers=%d" % (what, rva, len(callers)))
        for c in callers[:60]:
            r = S.enclosing(funcs, c)
            fn = ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "no pdata"
            off = S.va_to_off(secs, c)
            ctx = data[max(0, off - 16):off + 8]
            print("   caller rva=%#x  %s" % (c - S.IMAGE_BASE, fn))
            print("      ctx %s" % ctx.hex())

        # Absolute VA references anywhere (FF 15 disp32, 48 8D 0D/15, lea rax,[rip+x])
        pat = struct.pack("<Q", want)
        refs = []
        for s in secs:
            i = s["raw"]
            hi = s["raw"] + s["rawsize"]
            while True:
                i = data.find(pat, i, hi)
                if i < 0:
                    break
                refs.append((s["name"], S.IMAGE_BASE + s["va"] + (i - s["raw"])))
                i += 1
        print("   absolute u64 refs: %d" % len(refs))
        for sec, va in refs[:10]:
            print("      %s rva=%#x" % (sec, va - S.IMAGE_BASE))


if __name__ == "__main__":
    main()
