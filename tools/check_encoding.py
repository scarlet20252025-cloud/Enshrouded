r"""ASCII-only diagnostic: report lines in src/mod.cpp still containing U+FFFD."""
import io
import sys

PATH = r"E:\DSH\肥鱼乐园\WolfMount\src\mod.cpp"


def main():
    with io.open(PATH, encoding="utf-8") as f:
        lines = f.read().split("\n")
    hits = 0
    for i, ln in enumerate(lines, 1):
        if "\ufffd" in ln:
            hits += 1
            sys.stdout.write("LINE %d: %r\n" % (i, ln.encode("unicode_escape").decode("ascii")))
    sys.stdout.write("total bad lines: %d\n" % hits)
    sys.stdout.write("total lines: %d\n" % len(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
