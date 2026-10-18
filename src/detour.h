#pragma once
// ============================================================================
//  WolfMount — inline detour engine
//
//  A minimal x64 inline hook. Writes a 12-byte absolute jump
//  (mov rax, imm64; jmp rax) over the target and keeps a trampoline of the
//  overwritten bytes so the original can still be called.
//
//  This is intentionally tiny and auditable rather than a full detour library:
//  every address we patch is one we located by static analysis and will re-check
//  at runtime against the module base (ASLR-safe).
// ============================================================================

#include <windows.h>
#include <cstdint>

namespace wolfmount::detour {

// How many bytes the patch occupies, and therefore how much of the target's
// prologue the trampoline must steal.
//
//   Abs64 — `FF 25 00000000 <imm64>`: 14 bytes, reaches anywhere.
//   Rel32 — `E9 <rel32>`:              5 bytes, reaches ±2GB.
//
// Use Rel32 when the target function is SHORTER than 14 bytes (a leaf like
// `mov rax,[rcx]; mov rax,[rax+8]; ret` is only 8 bytes) — an Abs64 patch would
// overwrite the `ret` and run into the next function.
enum class PatchMode { Abs64, Rel32 };

struct Hook {
    void*   target   = nullptr;   // the function we patch
    void*   detour   = nullptr;   // our replacement
    void*   trampoline = nullptr; // executable copy of the stolen bytes + jump back
    void*   relay    = nullptr;   // Rel32 mode only: near-target Abs64 jump thunk
    PatchMode mode   = PatchMode::Abs64;
    // Longest x86-64 instruction is 15 bytes; allow margin for a 14-byte patch
    // that straddles up to 2 whole instructions.
    uint8_t origBytes[32] = {0};
    size_t  origLen   = 0;
    bool    installed = false;
};

// Install `hook->detour` at `hook->target`. Returns true on success.
bool Install(Hook* hook);

// Remove the hook and restore the original bytes.
bool Remove(Hook* hook);

// Allocate + populate the trampoline (run before Install).
bool CreateTrampoline(Hook* hook);

} // namespace wolfmount::detour
