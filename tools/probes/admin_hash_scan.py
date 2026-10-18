r"""Locate the admin-command *handlers* by their type-name strings.

Earlier we found the wire-format table at 0x141507400 (per-entry 0x40 bytes:
char* name, u32, u32, u64, u64 N, u64 N-8, u64 1, u64 0, ptr typedesc) with
0 readers. The handlers must be found another way: search .text for the
FNV-1a hash of each admin command TYPE, and also look for a hash->handler
jump table near 0x14047fc97's dispatcher family.

Print the hashes and their .text references with enclosing functions.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402

IB = S.IMAGE_BASE

NAMES = [
    "keen::ecs::AdminSpawnCommand",
    "keen::ecs::AdminKillFactionCommand",
    "keen::ecs::AdminTeleportAction",
    "keen::ecs::AdminApplyInventoryCommand",
    "keen::ecs::AdminSetDayTimeAction",
    "keen::ecs::AdminSetCharacterLevelAction",
    "keen::ecs::AdminPerkAction",
    "keen::ecs::AdminDestroyItemAction",
    "keen::ecs::AdminSetFlameLevelAction",
    "keen::ecs::AdminRepairAllItemsAction",
    "keen::ecs::AdminRefillAllFuelAction",
    "keen::ecs::AdminChangeGameSettingsAction",
    "keen::ecs::AdminDebugCameraDisplayAction",
    "keen::ecs::AdminDebugEnemyAction",
    "keen::ecs::AdminInventoryCreateAction",
]


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode():
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = IB + next(s["va"] for s in secs if s["name"] == ".text")

    for name in NAMES:
        h = fnv1a(name)
        hits = []
        for i in range(lo, hi - 4):
            if struct.unpack_from("<I", data, i)[0] == h:
                hits.append(tlo + (i - lo))
        print("%-46s 0x%08X  hits=%d" % (name, h, len(hits)))
        for a in hits[:6]:
            r = S.enclosing(funcs, a)
            print("     rva=%#x  %s" % (a - IB,
                  ("func rva=%#x size=%d" % (r[0] - IB, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
