// ============================================================================
//  WolfMount — inline detour engine (x64)
//
//  Absolute jump via the standard 12-byte sequence:
//      FF 25 00 00 00 00    jmp [rip+0]      (6 bytes)
//      <8 bytes absolute target address>
//
//  The trampoline copies enough whole instructions to cover 12 bytes, then
//  appends the same 12-byte jump back to (target + stolen_len).
//
//  Instruction lengths are computed with a small decoder that understands the
//  x64 encodings the game actually uses (REX prefixes, modrm, SIB, disp8/32,
//  imm8/32/64, RIP-relative). Good enough for hooking known call sites; we
//  never hook arbitrary/obfuscated code.
// ============================================================================

#include "detour.h"

#include <cstdio>
#include <cstring>

namespace wolfmount::detour {

namespace {

// Length of a single x86-64 instruction. Returns 0 if it cannot decode it.
size_t InsnLength(const uint8_t* p, size_t maxLen) {
    if (maxLen == 0) return 0;
    const uint8_t* start = p;
    // Legacy prefixes (group 1..4): F0, F2, F3, 66, 67, and REX 40..4F.
    size_t rex = 0;
    bool sawREX = false;
    while (true) {
        uint8_t b = *p;
        if (b == 0xF0 || b == 0xF2 || b == 0xF3 || b == 0x66 || b == 0x67 ||
            (b >= 0x40 && b <= 0x4F)) {
            if (b >= 0x40 && b <= 0x4F) { rex = b; sawREX = true; }
            ++p;
            if ((size_t)(p - start) >= maxLen) return 0;
            continue;
        }
        break;
    }
    (void)rex;

    // Opcode map: 0F escapes are two-byte opcodes.
    uint8_t op = *p++;
    if ((size_t)(p - start) >= maxLen) return 0;
    if (op == 0x0F) {
        op = *p++;
        if ((size_t)(p - start) >= maxLen) return 0;
    }

    // Operand-less / single-byte instructions with no ModRM.
    switch (op) {
        case 0xC3: case 0xCB: case 0xC2: case 0xCA:   // ret / ret imm16
            if (op == 0xC2 || op == 0xCA) { p += 2; }
            return (size_t)(p - start);
        case 0x90: case 0xCC: case 0xF4: case 0x9C: case 0x9D:
        case 0xFA: case 0xFB: case 0xFC: case 0xFD:
            return (size_t)(p - start);
        // push r64 (50-57) / pop r64 (58-5F): single byte, no modrm.
        case 0x50: case 0x51: case 0x52: case 0x53:
        case 0x54: case 0x55: case 0x56: case 0x57:
        case 0x58: case 0x59: case 0x5A: case 0x5B:
        case 0x5C: case 0x5D: case 0x5E: case 0x5F:
            return (size_t)(p - start);
        // push imm32 (68) / push imm8 (6A) have no modrm either.
        case 0x68: return (size_t)(p - start) + 4;
        case 0x6A: return (size_t)(p - start) + 1;
        // mov r64, imm64 (B8+rd with REX.W); else mov r32, imm32
        case 0xB8: case 0xB9: case 0xBA: case 0xBB:
        case 0xBC: case 0xBD: case 0xBE: case 0xBF:
            return (size_t)(p - start) + ((sawREX && (rex & 0x08)) ? 8 : 4);
        // mov r8, imm8 (B0-B7)
        case 0xB0: case 0xB1: case 0xB2: case 0xB3:
        case 0xB4: case 0xB5: case 0xB6: case 0xB7:
            return (size_t)(p - start) + 1;
        // E8/E9 rel32, EB rel8 (call/jmp rel)
        case 0xE8: case 0xE9: return (size_t)(p - start) + 4;
        case 0xEB: return (size_t)(p - start) + 1;
        // jcc rel8 (70-7F)
        case 0x70: case 0x71: case 0x72: case 0x73:
        case 0x74: case 0x75: case 0x76: case 0x77:
        case 0x78: case 0x79: case 0x7A: case 0x7B:
        case 0x7C: case 0x7D: case 0x7E: case 0x7F:
            return (size_t)(p - start) + 1;
        default: break;
    }

    // ModRM byte.
    uint8_t modrm = *p++;
    if ((size_t)(p - start) >= maxLen) return 0;
    uint8_t mod = (modrm >> 6) & 3;
    uint8_t rm  = modrm & 7;

    // SIB when mod != 3 and rm == 4.
    if (mod != 3 && rm == 4) {
        ++p;
        if ((size_t)(p - start) >= maxLen) return 0;
    }

    // Displacement.
    if (mod == 0 && rm == 5) {
        p += 4;                       // RIP-relative (or [disp32])
    } else if (mod == 1) {
        p += 1;
    } else if (mod == 2) {
        p += 4;
    }
    if ((size_t)(p - start) > maxLen) return 0;

    // Immediates for opcodes that DO have a ModRM and also take an immediate.
    switch (op) {
        case 0x80: case 0x81: case 0x83:          // group1 imm8/imm32
            p += (op == 0x81) ? 4 : 1;
            break;
        case 0xC6: case 0xC7:                     // mov r/m, imm8/imm32
            p += (op == 0xC7) ? 4 : 1;
            break;
        case 0x69:                                // imul r, r/m, imm32
            p += 4;
            break;
        case 0x6B:                                // imul r, r/m, imm8
            p += 1;
            break;
        default:
            break;   // most modrm opcodes have no immediate
    }

    return (size_t)(p - start);
}

} // anonymous namespace

bool CreateTrampoline(Hook* hook) {
    if (!hook || !hook->target || !hook->detour) return false;

    // The patch is 14 bytes (FF 25 00000000 + imm64) or 5 bytes (E9 rel32), so
    // we must steal at least that many bytes of the target to keep every whole
    // instruction intact.
    const size_t kPatchLen = (hook->mode == PatchMode::Rel32) ? 5 : 14;

    const uint8_t* target = reinterpret_cast<const uint8_t*>(hook->target);
    size_t total = 0;
    // InsnLength's maxLen is the remaining bytes it may READ. Give it a
    // generous window (an instruction is at most 15 bytes) rather than a
    // shrinking 16-total, which wrongly rejected an instruction straddling
    // the 14-byte patch boundary.
    while (total < kPatchLen) {
        size_t l = InsnLength(target + total, 16);
        if (l == 0) return false;
        total += l;
        if (total > 64) return false;   // sanity: no real prologue is this long
    }
    hook->origLen = total;
    memcpy(hook->origBytes, target, total);

    // Trampoline = stolen bytes + jmp back. 16-byte aligned executable page.
    uint8_t* tramp = reinterpret_cast<uint8_t*>(
        VirtualAlloc(nullptr, 64, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!tramp) return false;

    size_t off = 0;
    memcpy(tramp + off, hook->origBytes, total);
    off += total;

    tramp[off++] = 0xFF; tramp[off++] = 0x25;
    uint32_t z = 0; memcpy(tramp + off, &z, 4); off += 4;
    uintptr_t back = reinterpret_cast<uintptr_t>(target + total);
    memcpy(tramp + off, &back, 8); off += 8;

    hook->trampoline = tramp;
    return true;
}

// Allocate one page within ±2GB of `anchor`, so a 5-byte `E9 rel32` from
// `anchor` can reach it. Windows will not hand us arbitrary addresses, so we
// walk the address space outward from the target in 64KB steps and take the
// first hole. (`anchor`, not `near`, because windows.h defines `near` as a
// macro.)
static void* AllocateNear(void* anchor, size_t size) {
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    const uintptr_t gran = si.dwAllocationGranularity ? si.dwAllocationGranularity : 0x10000;

    uintptr_t base = reinterpret_cast<uintptr_t>(anchor);
    const uintptr_t minAddr = reinterpret_cast<uintptr_t>(si.lpMinimumApplicationAddress);
    const uintptr_t maxAddr = reinterpret_cast<uintptr_t>(si.lpMaximumApplicationAddress);
    // Keep a margin inside the ±2GB window so the rel32 computation stays valid
    // even after the allocation granularity rounding below.
    const uintptr_t kRange = 0x70000000ull;   // 1.75 GB

    for (uintptr_t step = 0; step < kRange; step += gran) {
        // Search downward first: our DLL usually sits at a low address and the
        // game image is high, so downward tends to find space sooner.
        uintptr_t down = base - step;
        if (down > base) down = 0;   // underflow guard
        if (down >= minAddr) {
            void* p = VirtualAlloc(reinterpret_cast<void*>(down), size,
                                   MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
            if (p) return p;
        }
        uintptr_t up = base + step;
        if (up < base) break;        // overflow guard
        if (up <= maxAddr) {
            void* p = VirtualAlloc(reinterpret_cast<void*>(up), size,
                                   MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
            if (p) return p;
        }
    }
    return nullptr;
}

bool Install(Hook* hook) {
    if (!hook || !hook->trampoline || hook->installed) return false;

    if (hook->mode == PatchMode::Rel32) {
        // E9 <rel32> is only 5 bytes, but it can only reach ±2GB. This DLL is
        // loaded far from the game image, so the direct delta is usually out of
        // range. Build a relay thunk inside the reachable window instead:
        //   target: E9 -> relay: FF 25 00000000 <imm64 detour>
        if (hook->origLen < 5) return false;

        int64_t direct = reinterpret_cast<int64_t>(hook->detour) -
                         (reinterpret_cast<int64_t>(hook->target) + 5);
        void* jumpTo = hook->detour;

        if (direct < INT32_MIN || direct > INT32_MAX) {
            if (!hook->relay) {
                void* relay = AllocateNear(hook->target, 64);
                if (!relay) return false;
                uint8_t thunk[14];
                thunk[0] = 0xFF; thunk[1] = 0x25;
                uint32_t z = 0; memcpy(thunk + 2, &z, 4);
                uintptr_t dest = reinterpret_cast<uintptr_t>(hook->detour);
                memcpy(thunk + 6, &dest, 8);
                memcpy(relay, thunk, sizeof(thunk));
                FlushInstructionCache(GetCurrentProcess(), relay, sizeof(thunk));
                hook->relay = relay;
            }
            jumpTo = hook->relay;
        }

        int64_t delta = reinterpret_cast<int64_t>(jumpTo) -
                        (reinterpret_cast<int64_t>(hook->target) + 5);
        if (delta < INT32_MIN || delta > INT32_MAX) return false;

        uint8_t patch[5];
        patch[0] = 0xE9;
        int32_t rel = static_cast<int32_t>(delta);
        memcpy(patch + 1, &rel, 4);

        DWORD old = 0;
        if (!VirtualProtect(hook->target, hook->origLen,
                            PAGE_EXECUTE_READWRITE, &old)) return false;
        memcpy(hook->target, patch, 5);
        if (hook->origLen > 5)
            memset(static_cast<uint8_t*>(hook->target) + 5, 0x90,
                   hook->origLen - 5);
        VirtualProtect(hook->target, hook->origLen, old, &old);

        FlushInstructionCache(GetCurrentProcess(), hook->target, hook->origLen);
        hook->installed = true;
        return true;
    }

    // Absolute jump: FF 25 00000000 + 8-byte target = 14 bytes.
    uint8_t patch[14];
    patch[0] = 0xFF; patch[1] = 0x25;
    uint32_t z = 0; memcpy(patch + 2, &z, 4);
    uintptr_t dest = reinterpret_cast<uintptr_t>(hook->detour);
    memcpy(patch + 6, &dest, 8);

    // Patch exactly hook->origLen bytes (the whole stolen instructions), so
    // the trampoline's jump-back lands on the first untouched instruction.
    // origLen is >= 14 and was chosen in CreateTrampoline.
    size_t n = hook->origLen;
    if (n < 14) n = 14;

    DWORD old = 0;
    if (!VirtualProtect(hook->target, n, PAGE_EXECUTE_READWRITE, &old)) return false;
    memcpy(hook->target, patch, 14);
    // Fill any remainder (between 14 and n) with NOPs so execution never falls
    // into half an instruction.
    if (n > 14) memset((uint8_t*)hook->target + 14, 0x90, n - 14);
    VirtualProtect(hook->target, n, old, &old);

    FlushInstructionCache(GetCurrentProcess(), hook->target, n);
    hook->installed = true;
    return true;
}

bool Remove(Hook* hook) {
    if (!hook || !hook->installed) return false;

    DWORD old = 0;
    VirtualProtect(hook->target, hook->origLen, PAGE_EXECUTE_READWRITE, &old);
    memcpy(hook->target, hook->origBytes, hook->origLen);
    VirtualProtect(hook->target, hook->origLen, old, &old);
    FlushInstructionCache(GetCurrentProcess(), hook->target, hook->origLen);

    // The near relay page (Rel32 + out-of-range detour) is ours to free.
    if (hook->relay) {
        VirtualFree(hook->relay, 0, MEM_RELEASE);
        hook->relay = nullptr;
    }

    hook->installed = false;
    return true;
}

} // namespace wolfmount::detour
