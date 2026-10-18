#pragma once
// ============================================================================
//  WolfMount — shared logging
//
//  Every module writes to the same file, next to the layer DLL (falling back
//  to %TEMP% when the game directory is not writable).
//
//  The log is the only diagnostic channel we have inside the game process:
//  the renderer is a Vulkan layer, so there is no console and the game's own
//  crash reporter does not know about us.
// ============================================================================

#include <windows.h>

#include <cstdarg>
#include <cstddef>
#include <cstdio>
#include <string>

namespace wolfmount::log {

// Path of this module, resolved from an address inside it.
inline void SelfPath(char* out, size_t n) {
    HMODULE h = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
                       GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)&SelfPath, &h);
    GetModuleFileNameA(h, out, (DWORD)n);
}

// Opens (appending) the log file. Returns nullptr if neither location works.
inline FILE* Open() {
    char path[MAX_PATH] = {0};
    SelfPath(path, MAX_PATH);

    std::string p = std::string(path) + ".log";
    FILE* f = fopen(p.c_str(), "a");
    if (f) return f;

    // Fall back to %TEMP%.
    char tmp[MAX_PATH] = {0};
    GetTempPathA(MAX_PATH, tmp);
    std::string t = std::string(tmp) + "wolfmount_layer.log";
    return fopen(t.c_str(), "a");
}

// Appends one line. Safe to call from any thread; opens the file lazily.
inline void Line(const char* fmt, ...) {
    static FILE* s_f = nullptr;
    if (!s_f) {
        s_f = Open();
        if (!s_f) return;
    }

    va_list ap;
    va_start(ap, fmt);
    vfprintf(s_f, fmt, ap);
    va_end(ap);
    fputc('\n', s_f);
    fflush(s_f);
}

} // namespace wolfmount::log

// Convenience macro: WM_MOD_LOG("...", args...)
#define WM_MOD_LOG(...) ::wolfmount::log::Line(__VA_ARGS__)
