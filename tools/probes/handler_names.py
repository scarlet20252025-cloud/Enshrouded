r"""Read the .pdata neighbourhood of the handler cluster and look for the
descriptor records that precede each handler (like the admin command table).

Also dump the strings around the descriptor strings to see if the tame handler
has a human-readable name (e.g. "TameWildlifeEvent") next to its function ptr.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def cstr(data, off, secs):
    for sec in secs:
        if sec["raw"] <= off < sec["raw"] + sec["rawsize"]:
            if sec["name"] not in (".rdata", ".data"):
                return None
            end = data.find(b"\0", off)
            if end < 0 or end - off > 200:
                return None
            try:
                s = data[off:end].decode("ascii")
            except UnicodeDecodeError:
                return None
            if len(s) >= 3 and all(32 <= ord(c) < 127 for c in s):
                return s
            return None
    return None


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)

    # Look for qwords in .rdata pointing at cluster functions, and read the
    # PRECEDING qwords as potential string pointers.
    cluster = (S.IMAGE_BASE + 0x47F700, S.IMAGE_BASE + 0x484500)
    for sec in secs:
        if sec["name"] != ".rdata":
            continue
        i = sec["raw"]
        hi = sec["raw"] + sec["rawsize"]
        while i + 8 <= hi:
            v = struct.unpack_from("<Q", data, i)[0]
            if cluster[0] <= v < cluster[1]:
                # Try to read a string from the 4 qwords before.
                cands = []
                for k in range(-6, 0):
                    o = i + k * 8
                    if o < sec["raw"]:
                        continue
                    q = struct.unpack_from("<Q", data, o)[0]
                    if q:
                        off = q - S.IMAGE_BASE - 0
                        # translate VA to file offset
                        fo = S.va_to_off(secs, q)
                        s = cstr(data, fo, secs) if fo else None
                        if s:
                            cands.append((k, s))
                if cands:
                    print("handler rva=%#x at rdata rva=%#x" % (
                        v - S.IMAGE_BASE,
                        S.IMAGE_BASE + sec["va"] + (i - sec["raw"])))
                    for k, s in cands:
                        print("    %+d: %r" % (k, s))
            i += 8


if __name__ == "__main__":
    main()
