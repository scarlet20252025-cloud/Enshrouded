r"""Locate the TameWildlifeEvent dispatch semantics.

The tame handler at rva 0x47d5bc walks an array of 24-byte descriptor pairs
and compares each record's first dword against 0x537B675C. The instructions
between the compare and the writes tell us the exact payload layout the engine
expects, which is the backend the `tame` console command needs.

Also dumps the reflection layout of every type the handler touches.
"""
import json
import subprocess
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

OBJDUMP = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
RD = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def dis(rva, n):
    va = S.IMAGE_BASE + rva
    r = subprocess.run(
        [OBJDUMP, "-d", "--start-address=%d" % va, "--stop-address=%d" % (va + n), EXE],
        capture_output=True, text=True, errors="replace")
    return (r.stdout or r.stderr).splitlines()


def main():
    lines = dis(0x47D5BC, 0x260)
    # Keep only the tame branch: 0x14047d700 .. 0x14047d7c3.
    keep = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("14047d7") or s.startswith("14047d6f"):
            keep.append(ln)
    print("=== TameWildlifeEvent branch (0x14047d700-0x14047d7c3) ===")
    for ln in keep:
        print(ln)

    d = json.load(open(RD, encoding="utf-8"))
    by_idx = {t["index"]: t for t in d["types"]}

    def show(idx):
        t = by_idx.get(idx)
        if not t:
            return
        qn = t.get("qualifiedName") or t.get("name")
        print("\n--- %s idx=%d size=%s ---" % (qn, t["index"], t.get("size")))
        for name, f in (t.get("structFields") or {}).items():
            print("  +%-5s %-30s %s" % (f.get("dataOffset"), name,
                                        by_idx.get(f.get("type"), {}).get("name")))

    print("\n=== reflection layout of touched types ===")
    for i in (1762, 1761, 137, 1562, 1554):
        show(i)

    # The 96-byte event: what does the handler actually read?
    print("\n=== key reads in the tame branch ===")
    for ln in keep:
        s = ln.strip()
        if any(k in s for k in ("(%rbx)", "(%r15)", "(%rsi)", "(%rdi)", "(%rbp)")):
            print("  " + s)


if __name__ == "__main__":
    main()
