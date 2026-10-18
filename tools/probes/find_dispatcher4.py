r"""My function-boundary detection was wrong (mid-instruction starts). Use
.pdata as the authority: for each of the 123 `callq *0x28(reg)` sites, find the
enclosing runtime function properly by searching .pdata for the greatest
BeginAddress <= site.

Then report functions that contain a call28 AND are large (> 2000 bytes),
which is what a program dispatcher would look like.
"""
import re
import struct
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

PAT_INSN = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$")
PAT_CALL28 = re.compile(r"callq?\s+\*0x28\(%r[a-z0-9]+\)")


def pdata_funcs():
    data = S.load()
    secs = S.sections(data)
    pd = next(s for s in secs if s["name"] == ".pdata")
    out = []
    for i in range(pd["rawsize"] // 12):
        beg, end, unw = struct.unpack_from("<III", data, pd["raw"] + i * 12)
        if beg or end:
            out.append((beg, end))
    out.sort()
    return out


def enclosing(funcs, rva):
    lo, hi = 0, len(funcs) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if funcs[mid][0] <= rva:
            best = funcs[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    if best and best[0] <= rva < best[1]:
        return best
    return None


def main():
    funcs = pdata_funcs()
    print("runtime functions:", len(funcs))

    proc = subprocess.Popen([OBJ, "-d", "--section=.text", EXE],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace", bufsize=1 << 20)
    sites = []
    for line in proc.stdout:
        m = PAT_INSN.match(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        if PAT_CALL28.search(m.group(3)):
            sites.append(addr - 0x140000000)
    proc.stdout.close()
    proc.wait()
    print("call28 sites:", len(sites))

    buckets = {}
    for s in sites:
        f = enclosing(funcs, s)
        if f:
            buckets.setdefault(f, []).append(s)

    print("distinct enclosing functions:", len(buckets))
    rows = sorted(buckets.items(), key=lambda kv: -(kv[0][1] - kv[0][0]))
    print()
    print("%-14s %-8s %-6s %s" % ("func rva", "size", "calls", "site rvas"))
    for (beg, end), ss in rows[:25]:
        print("%#-13x %-8d %-6d %s" % (beg, end - beg, len(ss),
                                       ", ".join(hex(x) for x in ss[:6])))


if __name__ == "__main__":
    main()
