"""Port the reusable Create-analysis tools onto tools/common.py.

The goal is that a community member can clone the repo and run these without
editing an absolute path in twelve files. Each tool keeps its own command line
and its own output; only the exe-path resolution changes.

Usage: python tools/port_tools_to_common.py [--dry-run]
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Files whose hardcoded EXE line should be replaced by common.exe_path().
PORT = [
    "tools/check_r8_reads.py",
    "tools/dump_create_regions.py",
    "tools/find_component_array_offset.py",
    "tools/find_desc18.py",
    "tools/pdata_range.py",
    "tools/prove_desc18_unused.py",
    "tools/rva_dis.py",
    "tools/trace_desc_reload.py",
    "tools/trace_e10.py",
    "tools/verify_deployed_strings.py",
    "tools/verify_desc_layout.py",
    "tools/verify_desc_layout2.py",
]

# The two shapes that appear across these files.
RE_ENV = re.compile(
    r'^EXE = os\.environ\.get\(\s*"[A-Z_]+"\s*,\s*\n?\s*r?"[^"]*"\)\s*$',
    re.MULTILINE)
RE_PLAIN = re.compile(r'^EXE = r?"[A-Za-z]:\\[^"]*"\s*$', re.MULTILINE)

REPLACEMENT = (
    "import common\n"
    "EXE = common.exe_path()\n"
    "if not EXE:\n"
    "    raise SystemExit(\n"
    "        'enshrouded.exe not found; set WOLFMOUNT_EXE or ENSHROUDED_EXE'\n"
    "        ' to the full path')")


def port(path, dry):
    full = os.path.join(ROOT, path)
    if not os.path.isfile(full):
        return "missing", None
    text = io.open(full, encoding="utf-8").read()
    if "common.exe_path()" in text:
        return "already", None
    if RE_ENV.search(text):
        new = RE_ENV.sub(REPLACEMENT, text, count=1)
    elif RE_PLAIN.search(text):
        new = RE_PLAIN.sub(REPLACEMENT, text, count=1)
    else:
        return "no-match", None
    if new == text:
        return "no-change", None
    if not dry:
        io.open(full, "w", encoding="utf-8", newline="\n").write(new)
    return "ported", new


def main():
    dry = "--dry-run" in sys.argv
    print("mode: %s" % ("dry run" if dry else "write"))
    bad = 0
    for p in PORT:
        state, _ = port(p, dry)
        print("  %-9s %s" % (state, p))
        if state in ("missing", "no-match"):
            bad += 1
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
