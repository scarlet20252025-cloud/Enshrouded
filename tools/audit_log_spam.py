"""统计日志刷屏构成：按行模式归类，算出每类的行数与字节占比。

用法：python tools/audit_log_spam.py <logfile>
"""
import os
import re
import sys
from collections import Counter

PATTERNS = [
    (re.compile(r"^\[wolfmount\] COMP #\d+"), "COMP"),
    (re.compile(r"^\[wolfmount\] ENQ #\d+"), "ENQ"),
    (re.compile(r"^\[wolfmount\] SEND #\d+"), "SEND"),
    (re.compile(r"^\[wolfmount\] overlay frame #\d+"), "overlay frame"),
    (re.compile(r"^\[wolfmount\] \*\*\* EXCEPTION"), "EXCEPTION(首行)"),
    (re.compile(r"^\[wolfmount\]     (faulting addr|raw address|instr bytes|access|rip=|rcx=)"), "EXCEPTION(续行)"),
    (re.compile(r"^\[wolfmount/entity\]"), "entity"),
    (re.compile(r"^\[wolfmount\]"), "wolfmount 其它"),
    (re.compile(r"^\["), "非 wolfmount"),
]


def main():
    path = sys.argv[1]
    total_bytes = os.path.getsize(path)
    counts = Counter()
    bytes_of = Counter()
    n = 0
    with open(path, "rb") as f:
        for raw in f:
            n += 1
            try:
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
            except Exception:
                line = ""
            key = "(other)"
            for pat, name in PATTERNS:
                if pat.search(line):
                    key = name
                    break
            counts[key] += 1
            bytes_of[key] += len(raw)
    print("文件: %s" % path)
    print("总行数: %d   总字节: %.2f MB" % (n, total_bytes / 1048576.0))
    print()
    print("%-20s %12s %10s %14s %10s" % ("模式", "行数", "占比", "字节", "占比"))
    print("-" * 70)
    for key, c in counts.most_common():
        b = bytes_of[key]
        print("%-20s %12d %9.2f%% %13.2fMB %9.2f%%"
              % (key, c, 100.0 * c / max(n, 1), b / 1048576.0,
                 100.0 * b / max(total_bytes, 1)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
