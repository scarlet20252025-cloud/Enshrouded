import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    if "payloadN" in s:
        print("already patched")
        return
    old = "        char hex[24 * 3 + 1];"
    new = "        char hex[24 * 3 + 1];\n        const int payloadN = n;"
    if old not in s:
        print("pattern A not found")
        return
    s = s.replace(old, new, 1)
    old2 = '        WM_MOD_LOG("[wolfmount]   payload(%u) %s", (unsigned)payload, hex);'
    new2 = '        if (payloadN <= 3000) {\n            WM_MOD_LOG("[wolfmount]   payload(%u) %s", (unsigned)payload, hex);\n        }'
    if old2 not in s:
        print("pattern B not found")
        return
    s = s.replace(old2, new2, 1)
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("bounded payload dump to the first 3000 records")


if __name__ == "__main__":
    main()
