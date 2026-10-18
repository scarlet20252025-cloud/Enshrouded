"""Repair the broken multi-line SystemExit left by port_tools_to_common.py.

The first version of the replacement text split a Python string literal across
two physical lines, which is a SyntaxError. This script rewrites that exact
broken block into a single valid statement, so the port does not have to be
redone from scratch.

Usage: python tools/fix_ported_systemexit.py [--dry-run]
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGETS = [
    "tools/check_r8_reads.py",
    "tools/dump_create_regions.py",
    "tools/find_component_array_offset.py",
    "tools/find_desc18.py",
    "tools/pdata_range.py",
    "tools/prove_desc18_unused.py",
    "tools/rva_dis.py",
    "tools/trace_desc_reload.py",
    "tools/trace_e10.py",
    "tools/verify_desc_layout.py",
    "tools/verify_desc_layout2.py",
]

BROKEN = (
    "    raise SystemExit('enshrouded.exe not found; set WOLFMOUNT_EXE or\n"
    "                      ENSHROUDED_EXE to the full path')")

FIXED = (
    "    raise SystemExit(\n"
    "        'enshrouded.exe not found; set WOLFMOUNT_EXE or ENSHROUDED_EXE'\n"
    "        ' to the full path')")


def main():
    dry = "--dry-run" in sys.argv
    print("mode: %s" % ("dry run" if dry else "write"))
    bad = 0
    for rel in TARGETS:
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            print("  missing  %s" % rel)
            bad += 1
            continue
        text = io.open(full, encoding="utf-8").read()
        if BROKEN not in text:
            if FIXED in text:
                print("  ok       %s" % rel)
            else:
                print("  nothing  %s" % rel)
            continue
        if not dry:
            io.open(full, "w", encoding="utf-8", newline="\n").write(
                text.replace(BROKEN, FIXED))
        print("  fixed    %s" % rel)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
