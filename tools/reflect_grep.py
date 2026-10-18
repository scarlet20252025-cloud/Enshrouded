"""Search reflection_data.json component/type names by substring."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "tools", "kfc", "reflection_data.json")


def main(argv):
    if len(argv) < 2:
        print("usage: python tools/reflect_grep.py <substring> [more...]")
        return 2
    data = json.load(open(PATH, encoding="utf-8"))
    types = data["types"] if isinstance(data, dict) and "types" in data else data
    needles = [a.lower() for a in argv[1:]]
    hits = 0
    for i, t in enumerate(types):
        name = str(t.get("qualifiedName") or t.get("name") or "")
        low = name.lower()
        if any(n in low for n in needles):
            print("idx=%-6d size=%-5s %s" % (i, t.get("size"), name))
            hits += 1
    print("\n%d hit(s)" % hits)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
