// ============================================================================
//  WolfMount — runtime ECS bridge
//
//  M2 scope: locate the game's ECS world and entity administration at runtime
//  so the mod can synthesise commands (AdminSpawnCommand, etc.).
//
//  Everything here is gated behind a successful signature probe. If the probe
//  fails the caller gets a clean "unavailable" rather than a crash, and the
//  menu reports which step failed.
// ============================================================================

#include "ecs.h"
#include "gamedata.h"

#include <windows.h>

#include <atomic>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <vector>

namespace wolfmount::ecs {

namespace {

// ---------------------------------------------------------------------------
//  Logging — mirrors the layer's log so all output lands in one file.
// ---------------------------------------------------------------------------
FILE* g_log = nullptr;

void LogOpen() {
    if (g_log) return;
    char path[MAX_PATH] = {0};
    HMODULE h = nullptr;
    GetModuleHandleExA(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        (LPCSTR)&LogOpen, &h);
    GetModuleFileNameA(h, path, MAX_PATH);
    std::string p = std::string(path) + ".log";
    g_log = fopen(p.c_str(), "a");
}

#define WM_ECS_LOG(...)                       \
    do {                                      \
        if (!g_log) LogOpen();                \
        if (g_log) {                          \
            fprintf(g_log, __VA_ARGS__);      \
            fputc('\n', g_log);               \
            fflush(g_log);                    \
        }                                     \
    } while (0)

// ---------------------------------------------------------------------------
//  Probes
//
//  We look for the admin-command registry string inside the module's read-only
//  data, then take a cross-reference to reach the dispatcher. The exact
//  dispatcher address is version specific, so we record what we found and let
//  the UI show it; we do NOT call anything we have not verified.
// ---------------------------------------------------------------------------

std::mutex            g_mu;
std::atomic<bool>     g_probed{false};
ProbeResult           g_probe;

// Find the first occurrence of an ASCII string in a LOADED module.
//
// The module is memory-mapped by the loader, so each section's bytes live at
// `base + VirtualAddress`, NOT at `base + PointerToRawData`. Using the raw
// file offset here reads torn/unmapped pages and faults — which is exactly
// what happened the first time this ran inside the game.
//
// For the on-disk equivalent (used by tools\ecs-selftest.cpp), PointerToRawData
// is the correct field. The two must not be confused.
uintptr_t FindString(HMODULE mod, const char* needle) {
    if (!mod || !needle) return 0;

    auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(mod);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE) return 0;
    auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(
        reinterpret_cast<const uint8_t*>(mod) + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return 0;

    const size_t n = strlen(needle);

    auto* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++sec) {
        // VirtualSize can be 0 for some sections; fall back to SizeOfRawData.
        size_t len = sec->Misc.VirtualSize
                   ? sec->Misc.VirtualSize
                   : sec->SizeOfRawData;
        if (len == 0) continue;

        const uint8_t* start =
            reinterpret_cast<const uint8_t*>(mod) + sec->VirtualAddress;

        if (n > len) continue;
        for (size_t off = 0; off + n <= len; ++off) {
            if (memcmp(start + off, needle, n) == 0) {
                return reinterpret_cast<uintptr_t>(start + off);
            }
        }
    }
    return 0;
}

HMODULE GameModule() {
    // The game's main executable, not our layer DLL.
    HMODULE h = GetModuleHandleA("enshrouded.exe");
    if (!h) h = GetModuleHandleA("enshrouded_server.exe");
    return h;
}

const char* SectionNameOf(HMODULE mod, uintptr_t addr) {
    if (!mod) return "?";
    auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(mod);
    auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(
        reinterpret_cast<const uint8_t*>(mod) + dos->e_lfanew);
    auto* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++sec) {
        uintptr_t va = reinterpret_cast<uintptr_t>(mod) + sec->VirtualAddress;
        if (addr >= va && addr < va + sec->Misc.VirtualSize) {
            static char buf[16] = {0};
            memcpy(buf, sec->Name, 8);
            return buf;
        }
    }
    return "?";
}

} // anonymous namespace

// ---------------------------------------------------------------------------
//  Probe
//
//  Records where the ECS command surface lives. This is deliberately read-only:
//  finding the strings proves the fields exist and lets us describe them, but
//  we do not fabricate calls until a target is verified dynamically.
// ---------------------------------------------------------------------------
const ProbeResult& Probe() {
    std::lock_guard<std::mutex> lk(g_mu);
    if (g_probed) return g_probe;

    g_probe = ProbeResult{};
    g_probe.module = GameModule();

    if (!g_probe.module) {
        g_probe.status = "game module not loaded";
        g_probed = true;
        WM_ECS_LOG("[wolfmount/ecs] probe failed: %s", g_probe.status);
        return g_probe;
    }

    // ---- admin command registry ------------------------------------------
    // "adminSpawnCommand" sits in the command-name table; its presence proves
    // the ECS command surface ships in this build.
    uintptr_t spawnCmd = FindString(g_probe.module, "adminSpawnCommand");
    if (spawnCmd) {
        g_probe.hasAdminSpawnCommand = true;
        g_probe.adminSpawnCommandStr = spawnCmd;
        g_probe.adminSpawnCommandSection = SectionNameOf(g_probe.module, spawnCmd);
    }

    // ---- admin enemy action (the taming entry) ----------------------------
    // "adminDebugEnemyAction" is the command that carries EnemyDebugAction,
    // whose enum includes SetTamed / ResetTamed.
    uintptr_t enemyAction = FindString(g_probe.module, "adminDebugEnemyAction");
    if (enemyAction) {
        g_probe.hasAdminEnemyAction = true;
        g_probe.adminEnemyActionStr = enemyAction;
    }

    // ---- the IsTame component and its behaviour docstring -----------------
    uintptr_t isTame = FindString(g_probe.module,
        "If set to false the Wildlife behavior won't run if the Wildlife is tamed");
    if (isTame) {
        g_probe.hasIsTameSemantics = true;
        g_probe.isTameDocStr = isTame;
    }

    // ---- taming event -----------------------------------------------------
    uintptr_t tameEvent = FindString(g_probe.module, "keenshrouded::actor::TameWildlifeEvent");
    if (!tameEvent) tameEvent = FindString(g_probe.module, "actor.TameWildlifeEvent");
    if (tameEvent) { g_probe.hasTameWildlifeEvent = true; g_probe.tameWildlifeEventStr = tameEvent; }

    // ---- the wolf's hook anchor -------------------------------------------
    uintptr_t hookAnchor = FindString(g_probe.module, "HookShotAnchorSubEntity");
    if (hookAnchor) { g_probe.hasHookAnchor = true; g_probe.hookAnchorStr = hookAnchor; }

    // ---- the mount hierarchy mechanism ------------------------------------
    uintptr_t hierarchy = FindString(g_probe.module, "addImpactHierarchy");
    if (hierarchy) { g_probe.hasImpactHierarchy = true; g_probe.hierarchyStr = hierarchy; }

    // ---- the fighting companion archetype ---------------------------------
    uintptr_t companion = FindString(g_probe.module, "keenshrouded::ecs::Enemy01BehaviorState");
    if (!companion) companion = FindString(g_probe.module, "ecs.Enemy01BehaviorState");
    if (companion) { g_probe.hasCompanionAI = true; g_probe.companionAIStr = companion; }

    int found = 0;
    if (g_probe.hasAdminSpawnCommand)   found++;
    if (g_probe.hasAdminEnemyAction)    found++;
    if (g_probe.hasIsTameSemantics)     found++;
    if (g_probe.hasTameWildlifeEvent)   found++;
    if (g_probe.hasHookAnchor)          found++;
    if (g_probe.hasImpactHierarchy)     found++;
    if (g_probe.hasCompanionAI)         found++;

    g_probe.featuresFound = found;
    g_probe.status = (found > 0) ? "ok" : "no ECS strings found";

    g_probed = true;
    WM_ECS_LOG("[wolfmount/ecs] probe: %s (%d/7 features)", g_probe.status, found);
    WM_ECS_LOG("[wolfmount/ecs]   adminSpawnCommand  @ %p [%s]",
               (void*)g_probe.adminSpawnCommandStr, g_probe.adminSpawnCommandSection);
    WM_ECS_LOG("[wolfmount/ecs]   adminEnemyAction   @ %p", (void*)g_probe.adminEnemyActionStr);
    WM_ECS_LOG("[wolfmount/ecs]   IsTame docstring   @ %p", (void*)g_probe.isTameDocStr);
    WM_ECS_LOG("[wolfmount/ecs]   TameWildlifeEvent  @ %p", (void*)g_probe.tameWildlifeEventStr);
    WM_ECS_LOG("[wolfmount/ecs]   HookAnchorSubEntity@ %p", (void*)g_probe.hookAnchorStr);
    WM_ECS_LOG("[wolfmount/ecs]   addImpactHierarchy @ %p", (void*)g_probe.hierarchyStr);
    WM_ECS_LOG("[wolfmount/ecs]   Enemy01Behavior    @ %p", (void*)g_probe.companionAIStr);

    return g_probe;
}

} // namespace wolfmount::ecs
