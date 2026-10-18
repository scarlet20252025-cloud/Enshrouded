r"""Recursively dump idx 1900 TameWildlifeEvent and its inheritance chain
(innerType 1762) with field offsets, so we can build the payload by hand.
"""
import io
import json

PATH = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def main():
    d = json.load(io.open(PATH, "r", encoding="utf-8"))
    types = d["types"]

    def rec(idx):
        return types[idx] if 0 <= idx < len(types) else None

    def walk(idx, depth=0):
        t = rec(idx)
        if t is None:
            return
        pad = "  " * depth
        print("%s[idx %d] %s  size=%s  innerType=%s" % (
            pad, idx, t.get("qualifiedName"), t.get("size"),
            t.get("innerType")))
        # fields may be inside a 'fields' key with different name
        fm = t.get("fields") or t.get("structFields")
        if isinstance(fm, dict):
            for name, meta in sorted(fm.items(),
                                     key=lambda kv: (kv[1] or {}).get("offset", 0)):
                if isinstance(meta, dict):
                    print("%s    +%-4s %-28s %s" % (pad, meta.get("offset"),
                                                    name,
                                                    meta.get("typeName")))
        inner = t.get("innerType")
        if isinstance(inner, int):
            walk(inner, depth + 1)

    walk(1900)
    print()
    print("--- idx 1762 ---")
    t = rec(1762)
    print(t and json.dumps({k: v for k, v in t.items()
                            if k != "namespace"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
