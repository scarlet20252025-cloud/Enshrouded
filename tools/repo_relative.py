"""Make the remaining WolfMount tools repo-relative.

`audit_hot_logs.py` and friends hard-code E:\\DSH\\... so they only run on the
machine that wrote them. They all read files that live inside this repository,
so the fix is to resolve the path from this file's own location instead.

Two shapes are handled:

    SRC   = r"E:\\DSH\\肥鱼乐园\\WolfMount\\src\\gamehooks.cpp"
    PATH  = "E:\\DSH\\肥鱼乐园\\WolfMount\\tools\\kfc\\..."

becomes

    ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SRC   = os.path.join(ROOT, "src", "gamehooks.cpp")

Anything that points at the game install (not this repo) is left alone and
reported, because that one genuinely belongs in an env var.

Usage: python tools/repo_relative.py [--dry-run]
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The repository path on the machine that wrote these tools, spelled both the
# way a raw string holds it (double backslashes) and the way a normal string
# holds it (single backslashes). Both forms must be rewritten.
REPO_RAW = r"E:\DSH" + "\\" + r"\u80a5\u9c7c\u4e50\u56ed" + "\\" + "WolfMount"
REPO_PLAIN = "E:\\DSH\\" + "\u80a5\u9c7c\u4e50\u56ed" + "\\WolfMount"
REPO_PREFIXES = (REPO_PLAIN, REPO_RAW)

# Only files whose absolute paths point inside this repo.
IN_REPO = [
    "tools/audit_hot_logs.py",
    "tools/check_encoding.py",
    "tools/classify_component.py",
    "tools/compare_components.py",
    "tools/desc_size.py",
    "tools/diff_templates.py",
    "tools/dump_type.py",
    "tools/find_wildlife_templates.py",
    "tools/fix_mod_encoding.py",
    "tools/index_templates.py",
    "tools/inspect_template.py",
    "tools/pdata_bounds.py",
    "tools/scanrefs.py",
    "tools/scan_msgreg.py",
    "tools/thunk_table.py",
]

# Match   NAME = r"<repo>\sub\path"    or    NAME = "<repo>\sub\path"
# and also the two-argument open(...) form:
#     open(r"<repo>\x.json", "r")
ASSIGN = re.compile(
    r'(?P<name>[A-Z_][A-Z0-9_]*)\s*=\s*(?P<pre>r?)"(?P<body>[^"\n]*)"')
OPEN_ARG = re.compile(
    r'(?P<pre>r?)"(?P<body>[^"\n]*)"')


def _tail(body):
    for pfx in REPO_PREFIXES:
        if body.startswith(pfx):
            return body[len(pfx):].lstrip("\\/")
    return None


def to_join(body):
    tail = _tail(body)
    if tail is None:
        return None
    parts = [p for p in re.split(r"[\\/]+", tail) if p]
    if not parts:
        return "ROOT"
    return "os.path.join(ROOT, %s)" % ", ".join('"%s"' % p for p in parts)


def ensure_os_import(text):
    if re.search(r"^import os$", text, re.MULTILINE):
        return text
    m = re.search(r"^import (\w+)$", text, re.MULTILINE)
    if m:
        return text[:m.start()] + "import os\n" + text[m.start():]
    return "import os\n" + text


def ensure_root(text):
    if re.search(r"^ROOT = ", text, re.MULTILINE):
        return text
    if "import os" not in text:
        text = ensure_os_import(text)
    m = re.search(r"^ROOT = ", text, re.MULTILINE)
    return text


def rewrite(text):
    """Replace every in-repo absolute path with a ROOT-relative expression.

    Returns (new_text, count). Paths that do not start with the repo prefix are
    left untouched, so the game-install path keeps whatever form it had.
    """
    count = [0]

    def repl(m):
        joined = to_join(m.group("body"))
        if joined is None:
            return m.group(0)
        count[0] += 1
        return "%s = %s" % (m.group("name"), joined)

    out = ASSIGN.sub(repl, text)

    def repl_open(m):
        joined = to_join(m.group("body"))
        if joined is None:
            return m.group(0)
        count[0] += 1
        # The string literal is GONE: what replaces it is the expression, not a
        # quoted version of the expression. Wrapping it in quotes again is how
        # the first version of this script produced
        #     sys.path.insert(0, "os.path.join(ROOT, \"tools\")")
        # which is a SyntaxError.
        return joined

    out = OPEN_ARG.sub(repl_open, out)
    return out, count[0]


def main():
    dry = "--dry-run" in sys.argv
    print("mode: %s" % ("dry run" if dry else "write"))
    bad = 0
    for rel in IN_REPO:
        full = os.path.join(ROOT, rel)
        if not os.path.isfile(full):
            print("  missing  %s" % rel)
            bad += 1
            continue
        text = io.open(full, encoding="utf-8").read()
        if REPO_PLAIN not in text and REPO_RAW not in text:
            print("  ok       %s" % rel)
            continue
        new, n = rewrite(text)
        if n == 0:
            print("  no-match %s" % rel)
            bad += 1
            continue
        new = ensure_os_import(new)
        if not re.search(r"^ROOT = ", new, re.MULTILINE):
            m = re.search(r"^import os$", new, re.MULTILINE)
            if m:
                new = (new[:m.end()] + "\n\nROOT = os.path.dirname("
                       "os.path.dirname(os.path.abspath(__file__)))"
                       + new[m.end():])
        if not dry:
            io.open(full, "w", encoding="utf-8", newline="\n").write(new)
        print("  ported   %s (%d path%s)" % (rel, n, "" if n == 1 else "s"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
