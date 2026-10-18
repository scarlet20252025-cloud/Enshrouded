#pragma once
// ============================================================================
//  WolfMount — ImGui assertion redirection
//
//  Force-included (clang -include) into every translation unit, BEFORE
//  imgui.h. This matters because imgui.h only defines IM_ASSERT if it is not
//  already defined — so defining it here wins everywhere.
//
//  Why this exists:
//    ImGui's default IM_ASSERT calls abort(). abort() is not an exception, so
//    a vectored exception handler never sees it, and the harness produces no
//    crash dump. The process simply vanishes. That is exactly how the first
//    playable build died inside ImGui_ImplVulkan_Init, with our log stopping
//    one line short of the failure and nothing else to go on.
//
//  With this header the failure becomes a log line naming the expression and
//  the source location, and execution continues to the caller's error check
//  instead of killing the game.
// ============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <string>

static void WolfMount_ImGuiAssertImpl(const char* expr, const char* file, int line) {
    char path[MAX_PATH] = {0};
    HMODULE h = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                       GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)&WolfMount_ImGuiAssertImpl, &h);
    GetModuleFileNameA(h, path, MAX_PATH);

    std::string p = std::string(path) + ".log";
    FILE* f = fopen(p.c_str(), "a");
    if (!f) return;

    fprintf(f, "[wolfmount] *** IMGUI ASSERT FAILED ***\n");
    fprintf(f, "    expr : %s\n", expr ? expr : "(null)");
    fprintf(f, "    at   : %s:%d\n", file ? file : "?", line);
    fflush(f);
    fclose(f);
}

#ifndef IM_ASSERT
#define IM_ASSERT(expr)                                          \
    do {                                                         \
        if (!(expr)) {                                           \
            WolfMount_ImGuiAssertImpl(#expr, __FILE__, __LINE__); \
        }                                                        \
    } while (0)
#endif
