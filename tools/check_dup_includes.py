"""Report files that include <cstdint> more than once.

The first version of tools/add_cstdint.py compared "<cstdint>" against a set
that had already had the brackets stripped, so it never noticed its own work and
would have inserted the include again on every run. That is fixed, but a file
already processed before the fix may carry a duplicate, so check for it
explicitly rather than assuming.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {".git", "build", "third_party", "probes", "scratch", "__pycache__",
        "gamecopy", "unpacked", "x64dbg", "work", "types"}

PAT = re.compile(r"#\s*include\s*[<\"]cstdint[>\"]")


def main():
    dups = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in sorted(filenames):
            if not name.endswith((".cpp", ".h", ".hpp")):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", errors="replace") as f:
                hits = len(PAT.findall(f.read()))
            if hits > 1:
                dups.append((os.path.relpath(path, ROOT), hits))

    if not dups:
        print("RESULT: PASS (no duplicate <cstdint> includes)")
        return 0
    print("RESULT: FAIL (%d file(s) include <cstdint> more than once)" % len(dups))
    for rel, n in dups:
        print("  %-46s x%d" % (rel, n))
    return 1


if __name__ == "__main__":
    sys.exit(main())
