r"""Locate the dispatch sites for the admin action types.

AdminSpawnCommand & friends never go through SendEvent, so their hash must be
compared somewhere else. This scans .text for the 4-byte immediates and shows
the surrounding bytes so the comparison shape is visible.
"""
import json
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

RD = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def admin_types():
    d = json.load(open(RD, encoding="utf-8"))
    out = []
    for t in d["types"]:
        qn = t.get("qualifiedName", "")
        if "Admin" in qn or "SpawnEntity" in qn or "TameWildlife" in qn:
            out.append((qn, t["qualifiedHash"], t.get("size"), t.get("index")))
    return sorted(out)


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)

    print("=== admin/spawn/tame action types (hash verified against FNV-1a) ===")
    for qn, h, size, idx in admin_types():
        calc = fnv1a(qn)
        mark = "OK " if calc == h else "MISMATCH(%08x)" % calc
        print("  %-58s idx=%-5s size=%-4s hash=%08X %s" % (qn, idx, size, h, mark))

    # Now scan .text for each hash immediate.
    lo, hi = S.text_span(secs)
    print("\n=== .text references ===")
    for qn, h, size, idx in admin_types():
        pat = struct.pack("<I", h)
        hits = []
        i = lo
        while True:
            i = data.find(pat, i, hi)
            if i < 0:
                break
            hits.append(i)
            i += 1
        if not hits:
            continue
        print("\n-- %s  hash=%08X  size=%s  %d refs" % (qn, h, size, len(hits)))
        for off in hits[:12]:
            va = S.off_to_va(secs, off)
            r = S.enclosing(funcs, va)
            fn = ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"
            # show 24 bytes before so the compare opcode is visible
            pre = data[max(lo, off - 24):off + 8]
            print("   rva=%#x  %s" % (va - S.IMAGE_BASE, fn))
            print("      %s" % pre.hex())


if __name__ == "__main__":
    main()
