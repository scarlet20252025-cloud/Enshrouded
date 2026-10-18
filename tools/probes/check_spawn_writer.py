r"""Check whether SpawnEntityEvent / TemplateReference has any writer in .text.

This decides whether `spawn` in the console can ever be backed by the game's
own spawn path.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
import scanrefs as S  # noqa: E402


def fnv1a(s):
    h = 0x811C9DC5
    for b in s.encode():
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


NAMES = [
    "keen::actor::SpawnEntityEvent",
    "keen::actor::SpawnEntityBaseEvent",
    "keen::ecs::TemplateReference",
    "keen::ecs::UnitTransformer",
    "keen::ecs::Animal",
    "keen::ecs::Wildlife",
    "keen::ecs::NetworkWildlife",
    "keen::ecs::IsTame",
    "keen::ecs::Faction",
    "keen::ecs::CurrentTransform",
    "keen::ecs::EntityDiedEvent",
    "keen::actor::TameWildlifeEvent",
    "keen::ecs::AdminSpawnCommand",
    "keen::ecs::PlayerFocus",
    "keen::ecs::Health",
]


def main():
    data = S.load()
    secs = S.sections(data)
    funcs = S.pdata_funcs(data, secs)
    lo, hi = S.text_span(secs)
    tlo = S.IMAGE_BASE + next(s["va"] for s in secs if s["name"] == ".text")

    for name in NAMES:
        h = fnv1a(name)
        hits = []
        for i in range(lo, hi - 4):
            if struct.unpack_from("<I", data, i)[0] == h:
                hits.append(tlo + (i - lo))
        # filter out metadata-only hits in .rdata
        real = []
        for a in hits:
            r = S.enclosing(funcs, a)
            real.append((a, r))
        print("%-40s 0x%08X  .text imm hits=%d" % (name, h, len(real)))
        for a, r in real[:8]:
            print("     rva=%#x  %s" % (a - S.IMAGE_BASE,
                  ("func rva=%#x size=%d" % (r[0] - S.IMAGE_BASE, r[1] - r[0])) if r else "?"))


if __name__ == "__main__":
    main()
