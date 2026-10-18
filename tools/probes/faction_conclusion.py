r"""Confirmed the tamed sabertooth's faction is 'Scavenger' — NOT PlayerAlly.

KEY FINDING that closes the faction question:
    Enemy_Wildbeast_wolf_earlygame        Faction = WildBeast
    Enemy_Scavenger_..._SnowSabertooth    Faction = WildBeast   (wild version)
    Enemy_Scavenger_..._SnowSabertooth_Tamed   Faction = Scavenger

So the game's own "tamed wildbeast" is a Scavenger-faction NPC unit. There is
NO shipped defensive-friendly wolf template. A wolf made tame by IsTame would
still be WildBeast(6) — same conclusion as the live test showed (it still bit
the player).

Therefore the only way to get a wolf that fights FOR the player is the
Faction write, and the ONLY run-time path we have not yet verified is the
24-byte-descriptor channel. The next step is verifying whether Enqueue can
carry a Faction write in a record shape the engine actually accepts.
"""
import io
import os
import re
import subprocess

OBJ = r"C:\Users\63526\coopanion-native-trial\toolchain\llvm-mingw-20261006-ucrt-x86_64\bin\llvm-objdump.exe"
EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"


def main():
    # Look for OTHER 1-byte tag components that ARE enqueued by the game, to
    # learn the true record shape for a 1-byte component in the Enqueue path.
    # We know SetIsTame uses size=0x6D and writes value at payload+0x60.
    # Check whether Faction ever appears as a .text immediate near a call to
    # Enqueue (0x140952400).
    pass


if __name__ == "__main__":
    main()
