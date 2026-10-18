r"""Component payloads are only observed as the *preceding* Enqueue record, but
Enqueue only logs the first 40 calls and FlushPendingComp only traces the first
400. Two problems:

1. The 400 limit was exhausted in the first seconds of world load (all
   `OverrideLevel`, size 76). Combat writes arrive later and are never traced.
2. The `ENQ #` cap of 40 means we do not see the queue depth/size of combat
   writes.

Raise the caps so a fight produces a readable trace. Keep the log bounded
(2000 records / hexdump of 24 bytes each) so the file does not explode.
"""
import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    n = 0

    a = "    if (n <= 40) {\n        WM_MOD_LOG(\"[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u\","
    b = "    if (n <= 200) {\n        WM_MOD_LOG(\"[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u\","
    if a in s:
        s = s.replace(a, b); n += 1

    c = "    if (n <= 400) {\n        const char* name = reflect::NameForHash(hash);"
    d = "    if (n <= 2000) {\n        const char* name = reflect::NameForHash(hash);"
    if c in s:
        s = s.replace(c, d); n += 1

    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("patched %d caps" % n)


if __name__ == "__main__":
    main()
