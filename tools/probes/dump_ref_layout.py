r"""Find the ObjectReference's own field layout — it is 16 bytes but has no
structFields, so its members come from the OBJECT_REFERENCE primitive. Compare
with another ObjectReference type that DOES carry fields (e.g. ItemReference at
+236 of SpawnEntityBaseEvent, or a Guid-based reference) to infer the layout.

Also dump keen::Guid and keen::WorldPosition / Offset / float3 sizes.
"""
import json
import os

RD = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "tools", "kfc", "reflection_data.json")


def main():
    d = json.load(open(RD, encoding="utf-8"))
    by_idx = {t["index"]: t for t in d["types"]}

    # 1) all OBJECT_REFERENCE / TYPEDEF types with structFields
    n = 0
    for t in d["types"]:
        if t.get("primitiveType") in ("OBJECT_REFERENCE", "TYPEDEF") and t.get("structFields"):
            n += 1
            if n <= 12:
                sf = t["structFields"]
                print("idx=%-5d %-46s %s" % (t["index"], t["qualifiedName"],
                      sorted((m["dataOffset"], f) for f, m in sf.items())[:6]))
    print("OBJECT_REFERENCE/TYPEDEF with fields:", n)

    print()
    for name in ("keen::Guid", "keen::WorldPosition", "keen::ecs::Offset",
                 "keen::float3", "keen::actor::SpawnEntityTransform",
                 "keen::ecs::TargetType", "keen::AttachmentSlot",
                 "keen::Time", "keen::VersionedData", "keen::bool",
                 "keen::skilltree_nodes::NodeReference", "keen::ItemReference"):
        for t in d["types"]:
            if t["qualifiedName"] == name:
                sf = t.get("structFields") or {}
                print("%-42s idx=%-5d size=%-4s prim=%-18s fields=%s" % (
                    name, t["index"], t.get("size"), t.get("primitiveType"),
                    sorted((m.get("dataOffset"), f) for f, m in sf.items())[:8]))
                break
        else:
            print("%-42s NOT FOUND" % name)


if __name__ == "__main__":
    main()
