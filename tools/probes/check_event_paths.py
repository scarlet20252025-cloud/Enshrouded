r"""Is there ANY static path that sends SpawnEntityEvent / TameWildlifeEvent?

We hook SendEvent (entry) and use it to push IsTame. If the game itself sends
SpawnEntityEvent through SendEvent / SendEventEx / the ARRAY24 batch interface,
then we can synthesise one from the DLL with no dispatcher at all — that is the
whole spawn backend the console is missing.

Prints, for each event type of interest:
  - which of the 3 submit interfaces references its hash
  - the enclosing .pdata function and size
"""
import re
import struct
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

TARGETS = {
    "keen::actor::SpawnEntityEvent": 0x0A0E833C,
    "keen::ecs::TameWildlifeEvent": 0x537B675C,
    "keen::ecs::EntityDiedEvent": 0x004BF3A0,
    "keen::ecs::HitEvent": 0xCC0D57E0,
}

PAT_INSN = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$")
PAT_IMM = re.compile(r"\$0x([0-9a-f]+)")


def pdata_funcs():
    data = S.load()
    pd = next(s for s in S.sections(data) if s["name"] == ".pdata")
    out = []
    for i in range(pd["rawsize"] // 12):
        beg, end, unw = struct.unpack_from("<III", data, pd["raw"] + i * 12)
        if beg or end:
            out.append((beg, end))
    out.sort()
    return out


def enclosing(funcs, rva):
    lo, hi, best = 0, len(funcs) - 1, None
    while lo <= hi:
        mid = (lo + hi) // 2
        if funcs[mid][0] <= rva:
            best = funcs[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return best if (best and best[0] <= rva < best[1]) else None


def main():
    funcs = pdata_funcs()
    hits = {k: [] for k in TARGETS}
    vals = {v: k for k, v in TARGETS.items()}

    proc = subprocess.Popen([OBJ, "-d", "--section=.text", EXE],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace", bufsize=1 << 20)
    n = 0
    for line in proc.stdout:
        m = PAT_INSN.match(line)
        if not m:
            continue
        n += 1
        text = m.group(3)
        mi = PAT_IMM.search(text)
        if not mi:
            continue
        try:
            val = int(mi.group(1), 16)
        except ValueError:
            continue
        if val in vals:
            hits[vals[val]].append((int(m.group(1), 16) - 0x140000000, text))
    proc.stdout.close()
    proc.wait()
    print("scanned %d instructions" % n)

    for name, sites in hits.items():
        print()
        print("=" * 72)
        print("%s  hash=%#x" % (name, TARGETS[name]))
        if not sites:
            print("   NO immediate reference anywhere in .text")
            continue
        byfunc = {}
        for rva, text in sites:
            f = enclosing(funcs, rva)
            byfunc.setdefault(f, []).append((rva, text))
        for f, ss in sorted(byfunc.items(), key=lambda kv: kv[0][0] if kv[0] else 0):
            if f:
                print("  func %#x..%#x (size %d)  x%d" % (f[0], f[1], f[1] - f[0], len(ss)))
            else:
                print("  <no .pdata enclosing>")
            for rva, text in ss:
                print("      %#x  %s" % (rva, text))


if __name__ == "__main__":
    main()
