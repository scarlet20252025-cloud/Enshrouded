import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    n = 0

    # Log volume was the cause of the "game creation failed" report: 25 MB /
    # 377k lines stalled the render loop. Cap both traces at 5000 records again.
    a = "    if (n <= 100000) {"
    b = "    if (n <= 5000) {"
    c = s.count(a)
    if c:
        s = s.replace(a, b)
        n += c

    # And keep the payload hexdump bounded to the first 3000 records.
    d = "        if (payloadN <= 3000) {"
    if d not in s:
        pass

    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("reverted %d trace caps to 5000 records" % n)


if __name__ == "__main__":
    main()
