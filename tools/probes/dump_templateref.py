r"""Dump TemplateReference + the wolf/enemy templates' GUIDs from unpacked resources."""
import glob
import json
import os
import sys

ROOT = r"E:\DSH\肥鱼乐园\WolfMount"
sys.path.insert(0, os.path.join(ROOT, "tools"))
import dump_type  # noqa: E402

REF = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")

WANT = [
    "keen::ecs::TemplateReference",
    "keen::actor::SpawnEntityEvent",
    "keen::actor::SpawnEntityBaseEvent",
    "keen::actor::SpawnEntityCommomEvent",
]


def main():
    with open(REF, "r", encoding="utf-8") as fh:
        rd = json.load(fh)
    by_idx = rd["by_idx"] if "by_idx" in rd else {str(v["idx"]): v for v in rd["types"]}
    for name in WANT:
        t = dump_type.ByName(name)
        if not t:
            print("MISSING %s" % name)
            continue
        print("=" * 70)
        print("%s  idx=%s size=%s align=%s" % (name, t.get("idx"), t.get("size"), t.get("alignment")))
        fields = t.get("structFields") or {}
        for fname, meta in sorted(fields.items(), key=lambda kv: kv[1].get("offset", 0)):
            off = meta.get("offset")
            sz = meta.get("size")
            tn = meta.get("typeName") or meta.get("type")
            print("   +%-4s %-34s %-40s size=%s" % (off, fname, tn, sz))


if __name__ == "__main__":
    main()
