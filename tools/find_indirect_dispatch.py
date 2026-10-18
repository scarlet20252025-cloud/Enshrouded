"""Walk the dispatcher chain by following indirect-call sinks.

find_callers.py answers "who calls X" only for direct E8/E9 rel32. The three
functions in the transformer path (QueryBuild 0x9BAB60, QueryRun 0x9B5A50,
ComponentRemove 0x9C5DF0, and the wrapper 0x9C5F20 used by the program-table
walker at 0xA16910) all have ZERO direct callers. That means every caller goes
through a register that was loaded earlier - i.e. through the slot array at
world+0x746350 whose entries are copied out of the descriptors.

So the dispatcher must load `slot = world+0x746350 + index*0x1f20` and then
call something derived from it. This tool finds every `call [reg+...]` and
`call reg` site inside the ten functions that already reference the slot
bases, plus every function that does `imul reg,reg,0x1f20`, and prints them
with enough surrounding bytes to see what the base register was.

Usage: python tools/find_indirect_dispatch.py
"""
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import pe_common

STRIDE = 0x1F20
BASES = [0x746360, 0x746350]

# call [reg+disp8] and call reg
CALL_IND = [
    (re.compile(rb"\xff[\x60-\x77]\x28"), "[reg+0x28]"),
    (re.compile(rb"\xff[\x60-\x77]\x30"), "[reg+0x30]"),
    (re.compile(rb"\xff[\x60-\x77]\x20"), "[reg+0x20]"),
    (re.compile(rb"\xff[\x60-\x77]\x38"), "[reg+0x38]"),
    (re.compile(rb"\xff[\x60-\x77]\x08"), "[reg+0x08]"),
    (re.compile(rb"\xff[\x60-\x77]\x18"), "[reg+0x18]"),
    (re.compile(rb"\xff[\xd0-\xd7]"), "reg"),
    (re.compile(rb"\xff[\xd8-\xdf]"), "far reg"),
]

STRIDE_RE = re.compile(
    rb"[\x48\x4d]\x69[\xc0-\xff]" + struct.pack("<i", STRIDE))

BASE_RES = []
for off in BASES:
    n = struct.pack("<i", off)
    BASE_RES.append((off, re.compile(rb"\x48\x8d[\x80-\xbf]" + n)))


def main():
    exe = common.exe_path()
    if not exe:
        raise SystemExit("enshrouded.exe not found; set WOLFMOUNT_EXE")
    data = open(exe, "rb").read()
    secs, base = pe_common.sections(exe)
    traw = tsize = None
    for name, va, raw, rsize, vsize in secs:
        if name == ".text":
            traw, tsize = raw, rsize
            break
    text = data[traw:traw + tsize]
    funcs = pe_common.runtime_functions(data)
    print(".text raw=0x%X size=0x%X, %d runtime functions" % (traw, tsize, len(funcs)))

    def size_of(fb):
        for b, e in funcs:
            if b == fb:
                return e - b
        return None

    # 1) functions that use the stride
    stride_funcs = {}
    for m in STRIDE_RE.finditer(text):
        f = pe_common.func_of(funcs, m.start())
        if f:
            stride_funcs.setdefault(f[0], []).append(m.start())
    print("\n=== functions with imul reg,reg,0x1F20 : %d ===" % len(stride_funcs))
    for fb in sorted(stride_funcs):
        print("  func 0x%08X (%s B)  stride-sites %s"
              % (fb, size_of(fb), ",".join("0x%X" % r for r in stride_funcs[fb])))

    # 2) functions that reference the base
    base_funcs = {}
    for off, pat in BASE_RES:
        for m in pat.finditer(text):
            f = pe_common.func_of(funcs, m.start())
            if f:
                base_funcs.setdefault(f[0], []).append((m.start(), off))
    print("\n=== functions with lea r64,[r+0x746350/0x746360] : %d ===" % len(base_funcs))
    for fb in sorted(base_funcs):
        print("  func 0x%08X (%s B)  %s"
              % (fb, size_of(fb),
                 ",".join("0x%X:base%X" % (r, o) for r, o in base_funcs[fb])))

    # 3) for the union of those functions, list every indirect call site
    interesting = set(stride_funcs) | set(base_funcs)
    print("\n=== indirect call sites inside those functions ===")
    for fb in sorted(interesting):
        b = e = None
        for b_, e_ in funcs:
            if b_ == fb:
                b, e = b_, e_
                break
        if b is None:
            continue
        body = text[b:e]
        hits = []
        for pat, label in CALL_IND:
            for m in pat.finditer(body):
                hits.append((b + m.start(), label))
        if not hits:
            continue
        print("  func 0x%08X (%s B): %d indirect calls" % (fb, size_of(fb), len(hits)))
        for rva, label in sorted(hits):
            print("      0x%08X  %s" % (rva, label))
    return 0


if __name__ == "__main__":
    sys.exit(main())
