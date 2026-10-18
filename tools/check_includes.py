"""Find source files that use fixed-width integer types without including
<cstdint> / <stdint.h>.

This exists because the project developed for months under llvm-mingw, whose
libc++ headers drag <cstdint> in transitively from almost anything. WinLibs'
headers do not, so files that had always compiled suddenly failed:

    tools/ecs-selftest.cpp:18:5: error: unknown type name 'uint32_t'

The lesson is that "it compiles" is a property of the toolchain, not of the
code, and the only way to know is to build with a second one. This script makes
that class of bug visible without a second toolchain.

Usage:  python tools/check_includes.py [--root DIR]
Exit:   0 = clean, 1 = missing includes found
"""
import argparse
import os
import re
import sys

INT_TYPES = re.compile(
    r"\b(u?int(?:8|16|32|64)_t|u?intptr_t|u?intmax_t|size_t|ptrdiff_t)\b"
)
# includes_in() returns bare names (no angle brackets or quotes), so these must
# be bare too. Getting this wrong makes the checker claim every file is missing
# the include even when it is present.
CSTDINT = ("cstdint", "stdint.h")
CSIZE = ("cstddef", "stddef.h", "cstdint", "stdint.h")

# Types that <cstdint> provides, versus ones <cstddef> provides. size_t and
# ptrdiff_t technically live in <cstddef>, but every real implementation also
# exposes them via <cstdint>, so treat either include as satisfying both. This
# keeps the check honest without being pedantic about a distinction that never
# causes a real build failure.
SKIP_DIRS = {".git", "build", "third_party", "probes", "scratch",
             "__pycache__", "gamecopy", "unpacked", "work", "types",
             "x64dbg"}  # x64dbg is a third-party SDK, not ours to edit


def includes_in(text):
    """Return the set of include targets in the file, normalised."""
    return set(re.findall(r"#\s*include\s*[<\"]([^>\"]+)[>\"]", text))


def check_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Ignore comments and string literals well enough for this purpose: we only
    # need to avoid matching prose in a comment, not to tokenise C++.
    code = re.sub(r"//[^\n]*", "", text)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)

    found = set(INT_TYPES.findall(code))
    if not found:
        return None

    incs = includes_in(text)
    has_cstdint = any(i in incs for i in CSTDINT)
    has_cstddef = any(i in incs for i in CSIZE)

    # size_t / ptrdiff_t alone are satisfied by <cstddef>.
    only_sized = found.issubset({"size_t", "ptrdiff_t"})
    if only_sized:
        if has_cstddef or has_cstdint:
            return None
    elif has_cstdint:
        return None

    return sorted(found)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    args = ap.parse_args()

    root = args.root
    problems = []
    checked = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in sorted(filenames):
            if not name.endswith((".cpp", ".h", ".hpp", ".cc")):
                continue
            path = os.path.join(dirpath, name)
            checked += 1
            missing = check_file(path)
            if missing:
                problems.append((os.path.relpath(path, root), missing))

    print("checked %d source files" % checked)
    if not problems:
        print("RESULT: PASS (no file uses fixed-width ints without <cstdint>)")
        return 0

    print("RESULT: FAIL (%d file(s) missing an include)" % len(problems))
    for rel, types in problems:
        print("  %-44s uses %s" % (rel, ", ".join(types)))
    return 1


if __name__ == "__main__":
    sys.exit(main())
