"""Shared, portable defaults for the WolfMount tools.

Every tool needs the game executable to disassemble. Hard-coding an absolute
path is how a tool becomes a "works only on the machine that wrote it" script,
so the path is resolved in this order:

    1. the WOLFMOUNT_EXE environment variable
    2. the ENSHROUDED_EXE environment variable
    3. the default Steam location, if it exists
    4. a shallow search of the obvious Steam libraries

Nothing here is Enshrouded-specific beyond the folder name, and nothing reads
the registry, so a tool built on it stays usable by anyone.

Usage from a tool in the same directory:

    import common
    exe = common.exe_path()
"""
import os

# Name the game installs under inside a Steam library.
GAME_SUBDIR = os.path.join("steamapps", "common", "Enshrouded")
GAME_EXE = "enshrouded.exe"

# Where Steam itself lives by default on Windows.
STEAM_DEFAULT = os.path.join(
    os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Steam")


def _candidate_dirs():
    out = []
    if os.path.isdir(STEAM_DEFAULT):
        out.append(STEAM_DEFAULT)
    for root in ("C:", "D:", "E:"):
        for name in ("Steam", "SteamLibrary"):
            out.append(os.path.join(root + os.sep, name))
    # Deduplicate while keeping order.
    seen = set()
    res = []
    for d in out:
        if d not in seen:
            seen.add(d)
            res.append(d)
    return res


def exe_path():
    """Absolute path to enshrouded.exe, or None if it cannot be found."""
    for var in ("WOLFMOUNT_EXE", "ENSHROUDED_EXE"):
        v = os.environ.get(var)
        if v and os.path.isfile(v):
            return v
        if v and os.path.isdir(v):
            cand = os.path.join(v, GAME_EXE)
            if os.path.isfile(cand):
                return cand
    for d in _candidate_dirs():
        cand = os.path.join(d, GAME_SUBDIR, GAME_EXE)
        if os.path.isfile(cand):
            return cand
    return None


IMAGE_BASE = 0x140000000


def rva_to_va(rva):
    return IMAGE_BASE + rva


def va_to_rva(va):
    return va - IMAGE_BASE
