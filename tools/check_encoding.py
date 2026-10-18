"""Report source lines containing U+FFFD (a destroyed character).

A PowerShell round-trip once turned 62 lines of src/mod.cpp into replacement
characters. This is the tool that found it and the check that keeps it found.

Usage:
  python tools/check_encoding.py              # every .cpp/.h under src/ and tools/
  python tools/check_encoding.py src/mod.cpp  # one file
  python tools/check_encoding.py src tools    # one or more directories
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPLACEMENT = "\ufffd"


def check_file(path):
    try:
        with io.open(path, encoding="utf-8") as f:
            lines = f.read().split("\n")
    except UnicodeDecodeError as e:
        print("%s: NOT VALID UTF-8 (%s)" % (path, e))
        return 1, 0
    hits = 0
    for i, ln in enumerate(lines, 1):
        if REPLACEMENT in ln:
            hits += 1
            print("%s:%d: %s" % (path, i,
                                 ln.encode("unicode_escape").decode("ascii")[:160]))
    return hits, len(lines)


def collect(targets):
    out = []
    for t in targets:
        p = t if os.path.isabs(t) else os.path.join(ROOT, t)
        if os.path.isfile(p):
            out.append(p)
            continue
        for dirpath, _dirnames, filenames in os.walk(p):
            for fn in filenames:
                if fn.endswith((".cpp", ".h")):
                    out.append(os.path.join(dirpath, fn))
    return sorted(out)


def main(argv):
    targets = argv[1:] or ["src", "tools"]
    files = collect(targets)
    if not files:
        print("no source files found under: %s" % ", ".join(targets))
        return 1

    total_bad = 0
    total_lines = 0
    for p in files:
        bad, lines = check_file(p)
        total_bad += bad
        total_lines += lines

    print("checked %d file(s), %d line(s)" % (len(files), total_lines))
    print("total bad lines: %d" % total_bad)
    return 0 if total_bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
