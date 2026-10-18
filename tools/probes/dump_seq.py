r"""Dump the SequenceEvent (idx 1761) base fields with real offsets, and the
ActionSequenceEvent derived part, so we know the exact byte layout of the
96-byte TameWildlifeEvent payload.

The reflection_data.json 'fields' layout differs from the structFields dict
form. Print the raw JSON of 1761 and 1762.
"""
import io
import json

PATH = r"E:\DSH\肥鱼乐园\WolfMount\tools\kfc\reflection_data.json"


def main():
    d = json.load(io.open(PATH, "r", encoding="utf-8"))
    for idx in (1761, 1762, 1900):
        t = d["types"][idx]
        print("=" * 72)
        print(json.dumps(t, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
