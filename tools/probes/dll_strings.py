#!/usr/bin/env python3
"""Extract CJK UTF-8 string literals from the built DLL.

Requires the literal to be null-terminated and to contain at least two CJK
characters, which filters out machine-code bytes that merely happen to form
valid UTF-8 triplets.
"""
import re
import sys

DLL = r"E:\DSH\肥鱼乐园\WolfMount\build\wolfmount_layer.dll"

# A literal: bytes that are printable ASCII or valid 3-byte CJK, then a NUL.
LIT = re.compile(
    rb"(?:\x20-\x7e|[\xe4-\xe9][\x80-\xbf]{2}|[\xef][\xbc-\xbf][\x80-\xbf])+",
)


def main(path=DLL):
    data = open(path, "rb").read()
    seen = []
    for m in LIT.finditer(data):
        end = m.end()
        if end >= len(data) or data[end] != 0:
            continue
        try:
            s = m.group().decode("utf-8")
        except UnicodeDecodeError:
            continue
        cjk = [c for c in s if "\u4e00" <= c <= "\u9fff"]
        if len(cjk) < 2:
            continue
        if s not in seen:
            seen.append(s)
    out = "\n".join(seen)
    sys.stdout.buffer.write(out.encode("utf-8"))


if __name__ == "__main__":
    main(*sys.argv[1:])
