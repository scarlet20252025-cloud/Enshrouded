"""Collapse repeated consecutive <cstdint> includes left by the drafting bug in
tools/add_cstdint.py.

Only touches runs of identical adjacent include lines, so a file that legitimately
includes <cstdint> in two separate blocks (there is no reason to, but be safe) is
left alone.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = {".git", "build", "third_party", "probes", "scratch", "__pycache__",
        "gamecopy", "unpacked", "x64dbg", "work", "types"}
PAT = re.compile(r"^\s*#\s*include\s*[<\"]cstdint[>\"]\s*$")


def main():
    fixed = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in sorted(filenames):
            if not name.endswith((".cpp", ".h", ".hpp")):
                continue
            path = os.path.join(dirpath, name)
            with open(path, encoding="utf-8", newline="") as f:
                text = f.read()
            nl = "\r\n" if "\r\n" in text else "\n"
            lines = text.split(nl)

            out = []
            removed = 0
            for line in lines:
                if PAT.match(line) and out and PAT.match(out[-1]):
                    removed += 1
                    continue
                out.append(line)

            if removed:
                fixed.append((os.path.relpath(path, ROOT), removed))
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(nl.join(out))

    if not fixed:
        print("RESULT: PASS (nothing to collapse)")
        return 0
    print("collapsed %d duplicate line(s) across %d file(s)"
          % (sum(n for _, n in fixed), len(fixed)))
    for rel, n in fixed:
        print("  %-46s -%d" % (rel, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
