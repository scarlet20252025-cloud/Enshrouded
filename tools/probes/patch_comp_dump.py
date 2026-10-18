r"""Add a hex+name dump of each pending Enqueue record.

FlushPendingComp currently logs only the hash. To learn the true component
record shape (we need Faction's) we want the payload bytes too.
"""
import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"

OLD = '''    const int n = g_compSeen.fetch_add(1) + 1;
    // Only the first few hundred are interesting, and only for named types —
    // the reflection table turns the hash into the component's qualified name,
    // which is what makes this trace readable.
    if (n <= 400) {
        const char* name = reflect::NameForHash(hash);
        if (name && name[0]) {
            WM_MOD_LOG("[wolfmount] COMP #%d %s (0x%08X) size=%u eid=%u",
                       n, name, hash, (unsigned)size, eid);
        } else {
            WM_MOD_LOG("[wolfmount] COMP #%d 0x%08X size=%u eid=%u",
                       n, hash, (unsigned)size, eid);
        }
    }
}'''

NEW = '''    const int n = g_compSeen.fetch_add(1) + 1;
    // Only the first few hundred are interesting, and only for named types —
    // the reflection table turns the hash into the component's qualified name,
    // which is what makes this trace readable.
    if (n <= 400) {
        const char* name = reflect::NameForHash(hash);
        if (name && name[0]) {
            WM_MOD_LOG("[wolfmount] COMP #%d %s (0x%08X) size=%u eid=%u",
                       n, name, hash, (unsigned)size, eid);
        } else {
            WM_MOD_LOG("[wolfmount] COMP #%d 0x%08X size=%u eid=%u",
                       n, hash, (unsigned)size, eid);
        }
        // Dump the payload bytes too. `size` is the record size and the payload
        // starts at +0x0C, so the value region is size-0x0C bytes. Bounding the
        // dump keeps the log readable: components we care about (Faction, IsTame)
        // are 1-2 bytes.
        char hex[24 * 3 + 1];
        const uint16_t payload = (uint16_t)(size > 0x0C ? size - 0x0C : 0);
        const uint16_t dumpN = payload < 24 ? payload : 24;
        size_t w = 0;
        for (uint16_t i = 0; i < dumpN && w + 3 < sizeof(hex); ++i) {
            w += (size_t)snprintf(hex + w, sizeof(hex) - w, "%02X ", rec[0x0C + i]);
        }
        if (payload > dumpN) {
            snprintf(hex + w, sizeof(hex) - w, "...");
        }
        WM_MOD_LOG("[wolfmount]   payload(%u) %s", (unsigned)payload, hex);
    }
}'''


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    if OLD not in s:
        print("OLD block not found — aborting")
        return
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s.replace(OLD, NEW))
    print("patched FlushPendingComp with a payload hexdump")


if __name__ == "__main__":
    main()
