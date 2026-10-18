r"""Do component reads use Enqueue-shaped records, or a different field?

The claim that killed our Faction write was "Faction goes through the
24-byte descriptor array". Let's check the reverse: find a run-time consumer
that reads faction from an entity, and see what shape it expects.

Search for the Faction hash 0xA1F30F21 as a data literal in .rdata (pointer
dereferences / switch tables) — not as a .text immediate.

A second, cheaper idea already validated by reflection: every component write
in the Enqueue path has the record layout
    rec+0x00 u16 size
    rec+0x02 u8  flags
    rec+0x03 u8  0
    rec+0x04 u16 ctx+0x28
    rec+0x06 u16 ctx+0x2A
    rec+0x08 u32 entityId
    rec+0x0C payload (starts with u32 typeHash)
so the 'component type hash' at payload+0 is how the engine dispatches. If
Faction is never enqueued by the game itself, then Enqueue is simply the wrong
channel and the only fix is the spawn-descriptor channel.

Check whether SetFaction's other 10 call sites all live in spawn-pack
builders, or whether some live in a run-time path we could hook.
"""
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"

# Faction sites recorded earlier
SITES = [0x14021C3AA, 0x140222863, 0x14027D0CF, 0x1402E1E44, 0x140326437,
         0x140342AB6, 0x140346EC4, 0x1403ADF3C, 0x1403E521F, 0x140E3339F,
         0x14021D572]


def main():
    for s in SITES:
        r = subprocess.run([OBJ, "-d", "--start-address=%#x" % (s - 0x18),
                           "--stop-address=%#x" % (s + 0x18), EXE],
                           capture_output=True, text=True, errors="replace")
        ctx = []
        for ln in (r.stdout or "").splitlines():
            mM = "\#x" if False else re.match(
                r"^\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(\S.*)$", ln)
            if mM:
                ctx.append("%#-9x %s" % (int(mM.group(1), 16) - 0x140000000,
                                        mM.group(3).strip()))
        print("=" * 66)
        for ln in ctx:
            print(" ", ln)


if __name__ == "__main__":
    main()
