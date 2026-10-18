r"""Dump key spawn/tame related reflection types with full field layout."""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import dump_type as DT  # noqa: E402

WANT = [
    "keen::ecs::TemplateReference",
    "keen::actor::SpawnEntityBaseEvent",
    "keen::actor::SpawnEntityEvent",
    "keen::actor::TameWildlifeEvent",
    "keen::ecs::UnitTransformer",
    "keen::ecs::WildlifeTransformer",
    "keen::ecs::IsTame",
    "keen::ecs::DynamicEnemy01BehaviorState",
]


def main():
    d, by_idx = DT.load()
    for name in WANT:
        # build name -> index
        idx = None
        for t in d["types"]:
            if t.get("qualifiedName") == name or t.get("name") == name:
                idx = t["index"]
                break
        if idx is None:
            print("MISSING %s" % name)
            continue
        t = by_idx[idx]
        print("=" * 72)
        print("%s   index=%s size=%s align=%s  parent=%s" % (
            name, t.get("index"), t.get("size"), t.get("alignment"), t.get("baseType")))
        fields = t.get("structFields") or {}
        for fname, meta in sorted(fields.items(), key=lambda kv: kv[1].get("offset", 0)):
            inner = meta.get("type")
            inner_name = ""
            it = by_idx.get(inner)
            if it:
                inner_name = it.get("qualifiedName") or it.get("name")
            print("   +%-5s %-36s %-42s size=%s" % (
                meta.get("offset"), fname, inner_name or ("prim:" + str(meta.get("primitiveType"))),
                meta.get("size")))


if __name__ == "__main__":
    main()
