r"""Scan the full disassembly for the ECS program dispatcher.

Requirement: a function that BOTH
  (a) contains an indirect call through +0x28 (the handler slot field), and
  (b) references the program table (0x746350 / 0x746360 / 0x745a58 / 0x1f20).

Approach: walk the disassembly once, group instructions by enclosing function
(using `retq`/padding boundaries), then report functions satisfying both.
"""
import re
import subprocess
import sys

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

PAT_INSN = re.compile(r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$")
PAT_CALL28 = re.compile(r"callq?\s+\*0x28\(%r[a-z0-9]+\)")
PAT_TABLE = re.compile(r"0x746350|0x746360|0x745a48|0x745a58|0x743b10|\$0x1f20|0x1f20,")
PAT_FUNC_START = re.compile(r"^0000000000000000 <\.text>:$")


def main():
    proc = subprocess.Popen([OBJ, "-d", "--section=.text", EXE],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace", bufsize=1 << 20)

    cur_func = None
    funcs = {}          # start -> {"call28": [addrs], "table": [addrs]}
    order = []
    ncall = 0
    for line in proc.stdout:
        m = PAT_INSN.match(line)
        if not m:
            continue
        addr = int(m.group(1), 16)
        text = m.group(3).strip()
        if PAT_CALL28.search(text):
            ncall += 1
        # A new function starts right after `retq` + int3 padding, or after a
        # `nop` alignment block. We approximate by tracking retq.
        if text.startswith("retq"):
            if cur_func is not None:
                cur_func = None
            continue
        if cur_func is None:
            cur_func = addr
            order.append(cur_func)
            funcs[cur_func] = {"call28": [], "table": []}
        if PAT_CALL28.search(text):
            funcs[cur_func]["call28"].append(addr)
        if PAT_TABLE.search(text):
            funcs[cur_func]["table"].append(addr)

    proc.stdout.close()
    proc.wait()

    print("total callq *0x28(reg) sites:", ncall)
    both = [f for f in order if funcs[f]["call28"] and funcs[f]["table"]]
    print("functions with BOTH an indirect *0x28 call and a program-table ref:",
          len(both))
    for f in both[:20]:
        print("  func rva=%#x  call28=%d table=%d" % (
            f - 0x140000000, len(funcs[f]["call28"]), len(funcs[f]["table"])))
        for a in funcs[f]["call28"][:3]:
            print("      call28 at %#x" % (a - 0x140000000))

    only_call = [f for f in order if funcs[f]["call28"] and not funcs[f]["table"]]
    print()
    print("functions with *0x28 call but NO table ref:", len(only_call))
    for f in only_call[:30]:
        print("  func rva=%#x  call28=%d" % (f - 0x140000000,
                                             len(funcs[f]["call28"])))


if __name__ == "__main__":
    main()
