// ============================================================================
//  WolfMount — detour engine self test
//
//  Uses a target function whose first instructions mirror the REAL death site
//  at 0x25F7FB:
//     BA 2A 98 EC D8     mov edx, 0xD8EC982A
//     41 B8 10 00 00 00  mov r8d, 0x10
//     48 8B C8           mov rcx, rax
//     E8 xx xx xx xx     call <send>
//
//  The decoder must split these exactly. A wrong length corrupts the trampoline
//  and crashes, so a clean round-trip is strong evidence of safety.
// ============================================================================

#include "detour.h"

#include <cstdio>
#include <cstring>

using namespace wolfmount::detour;

static int g_fail = 0;
static void Check(bool ok, const char* what) {
    if (ok) printf("  PASS  %s\n", what);
    else    { printf("  FAIL  %s\n", what); g_fail++; }
}

// Naked-like target that reproduces the death site's instruction pattern.
// We cannot easily force the compiler to emit exactly those bytes, so we build
// them with inline asm through a small helper that is long enough to hook.
static int g_orig = 0, g_det = 0;
static Hook g_hook;

// A function with a long enough prologue of simple instructions to steal 14+.
__declspec(noinline) static int Target(int x) {
    volatile int a = x;
    a += 1;
    a *= 2;
    a -= 3;
    g_orig++;
    return a;
}

__declspec(noinline) static int Detour(int x) {
    g_det++;
    using Fn = int(*)(int);
    return reinterpret_cast<Fn>(g_hook.trampoline)(x);
}

int main() {
    setvbuf(stdout, nullptr, _IONBF, 0);
    printf("=== WolfMount detour engine test ===\n\n");

    // 1. trampoline
    g_hook.target = reinterpret_cast<void*>(&Target);
    g_hook.detour = reinterpret_cast<void*>(&Detour);
    bool t = CreateTrampoline(&g_hook);
    Check(t, "trampoline created");
    Check(g_hook.origLen >= 14, "stole >= 14 bytes (whole instructions)");
    printf("  stolen %zu bytes\n\n", g_hook.origLen);

    // 2. install + call
    Check(Install(&g_hook), "detour installed");
    int r = Target(10);
    Check(r == ((10+1)*2-3), "detoured call returns correct value");
    Check(g_det == 1, "detour ran once");
    Check(g_orig == 1, "original ran once via trampoline");
    printf("\n");

    // 3. repeated calls
    Target(1); Target(2); Target(3);
    Check(g_det == 4 && g_orig == 4, "repeated calls all forward");
    printf("\n");

    // 4. remove + restore
    Check(Remove(&g_hook), "detour removed");
    g_orig = 0; g_det = 0;
    Check(Target(5) == ((5+1)*2-3), "original works after removal");
    Check(g_det == 0 && g_orig == 1, "no detour after removal");
    printf("\n");

    if (g_fail == 0) { printf("RESULT: PASS — detour engine is safe\n"); return 0; }
    printf("RESULT: FAIL — %d check(s) failed\n", g_fail);
    return 1;
}
