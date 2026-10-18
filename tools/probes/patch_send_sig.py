r"""Refine the SendEvent hook: log every call, with its real argument names.

The body at rva 0x955400 is now fully decoded:

    void* SendEvent(void* buf, uint32_t value, uint32_t typeTag, size_t size)

    buf        = {void* data @0; size_t capacity @8; u32 writeIndex @0x10}
    value      -> [slot+0] as u32
    size       -> [slot+4] as u16
    typeTag    -> [slot+6] as u8, and MUST be < 0x100 (checked at +0x0E)
    payload    = slot+8, zeroed by memset
    return     = slot + 8

Our detour documents these as (buffer, hash, size, entityId), which is wrong.
The names do not change the ABI, so the hook still works — but the log lines
claiming "HitEvent ... entityId" are misdescribed, and the code path filtering
on `hash == 0xCC0D57E0 && size == 248` is looking for a typeTag that can never
be 0xCC0D57E0 (it is a u8!). That filter has never matched; the "HIT #" lines we
saw earlier must have come from the Enqueue-side trace or a different code path.

Correct behaviour:
  - Rename the parameters and log both names.
  - Drop the HitEvent-from-SendEvent theory, but keep a bounded trace of every
    call so we can find which queue `buf` is and which values flow through.
  - Keep the trampoline call and the pending-read mechanism (harmless).

Also: the earlier claim "HIT #1..9 target=6902 source=1 weapon=6825" cannot have
come from this filter, so we must not rely on it. The log below will tell us
what actually goes through SendEvent.
"""
import io

SRC = r"E:\DSH\肥鱼乐园\WolfMount\src\gamehooks.cpp"

OLD_SIG = """void* DetourSendEvent(void* buffer, uint32_t hash, uint32_t size, uint32_t entityId) {
    // 1. Flush whatever the previous call produced — its fields are complete now.
    FlushPendingHit();

    // 2. Perform the real write.
    void* record = g_trampoline
        ? g_trampoline(buffer, hash, size, entityId)
        : nullptr;

    // 3. Remember this HitEvent; we read it after the caller fills it in.
    if (record && hash == rva::HitEventHash && size == rva::HitEventSize) {
        g_pendingHit = static_cast<const uint8_t*>(record);
    }

    return record;
}"""

NEW_SIG = """void* DetourSendEvent(void* buffer, uint32_t value, uint32_t typeTag, size_t size) {
    // 1. Flush whatever the previous call produced — its fields are complete now.
    FlushPendingHit();

    // 2. Perform the real write.
    void* record = g_trampoline
        ? g_trampoline(buffer, value, typeTag, (uint32_t)size)
        : nullptr;

    // 3. Bounded trace. The body rejects typeTag >= 0x100, so this queue is a
    //    small-tag integer channel — not the FNV-hash event bus we once thought.
    //    Logging every call is the only way to learn what actually uses it.
    const int n = g_sendCount.fetch_add(1, std::memory_order_relaxed) + 1;
    if (n <= 60) {
        WM_MOD_LOG("[wolfmount] SEND #%d buf=%p value=%u tag=%u size=%u -> %p",
                   n, buffer, value, (unsigned)typeTag, (unsigned)size, record);
    }
    if (record && typeTag < 0x100) {
        g_pendingHit = static_cast<const uint8_t*>(record) - 8;
    }

    return record;
}"""


def main():
    s = io.open(SRC, "r", encoding="utf-8").read()
    if OLD_SIG not in s:
        print("OLD block not found — aborting")
        return
    s = s.replace(OLD_SIG, NEW_SIG)
    io.open(SRC, "w", encoding="utf-8", newline="\n").write(s)
    print("rewrote DetourSendEvent with the decoded signature")


if __name__ == "__main__":
    main()
