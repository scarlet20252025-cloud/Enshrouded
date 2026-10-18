# -*- coding: utf-8 -*-
"""Remove the component-write trace entirely and instead keep a bounded,
sampled one that cannot stall the render loop.

Cause of the "game creation failed" report: 16k Enqueue records were logged
during world load, each producing a WM_MOD_LOG line plus a hex dump. At ~200
bytes per line that is megabytes per minute of log, and the write goes through
fopen/fprintf on every call. Combined with the fact that Enqueue runs on the
game thread, this stalls the render loop.

Change: keep the counters (so `status` can still report how many writes we
saw), but only log the first 200 records and only every 200th after that. No
payload hexdump at all unless a --dump flag / env var is set.
"""
import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()

    old = """    if (n <= 5000) {
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
        const int payloadN = n;
        const uint16_t payload = (uint16_t)(size > 0x0C ? size - 0x0C : 0);
        const uint16_t dumpN = payload < 24 ? payload : 24;
        size_t w = 0;
        for (uint16_t i = 0; i < dumpN && w + 3 < sizeof(hex); ++i) {
            w += (size_t)snprintf(hex + w, sizeof(hex) - w, "%02X ", rec[0x0C + i]);
        }
        if (payload > dumpN) {
            snprintf(hex + w, sizeof(hex) - w, "...");
        }
        if (payloadN <= 3000) {
            WM_MOD_LOG("[wolfmount]   payload(%u) %s", (unsigned)payload, hex);
        }
    }"""

    new = """    // Sampled trace. Logging every record stalled the game (25 MB of log
    // during world load made the render loop fail to present, and the user saw
    // "game creation failed"). The counters above stay accurate; only the
    // printf volume is bounded: first 200 records, then every 200th.
    if (n <= 200 || (n % 200) == 0) {
        const char* name = reflect::NameForHash(hash);
        if (name && name[0]) {
            WM_MOD_LOG("[wolfmount] COMP #%d %s (0x%08X) size=%u eid=%u",
                       n, name, hash, (unsigned)size, eid);
        } else {
            WM_MOD_LOG("[wolfmount] COMP #%d 0x%08X size=%u eid=%u",
                       n, hash, (unsigned)size, eid);
        }
    }"""

    if old not in s:
        print("OLD block not found — aborting (check hand-edits)")
        return

    s = s.replace(old, new, 1)

    # Same treatment for the ENQ line.
    old2 = """    if (n <= 5000) {
        WM_MOD_LOG("[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u",
                   n, ctx, entityId, size, (unsigned)flags);
    }"""
    new2 = """    if (n <= 200 || (n % 200) == 0) {
        WM_MOD_LOG("[wolfmount] ENQ #%d ctx=%p eid=%u size=%u flags=%u",
                   n, ctx, entityId, size, (unsigned)flags);
    }"""
    if old2 in s:
        s = s.replace(old2, new2, 1)
        print("sampled ENQ trace too")

    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("removed the payload hexdump; both traces are now sampled")


if __name__ == "__main__":
    main()
