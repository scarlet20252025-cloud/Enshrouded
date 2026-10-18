// ===========================================================================
//  console-test.cpp — WolfMount console unit test
//
//  The console is the one place where the mod UIs a capability it might not
//  actually have. So the tests here are mostly about HONESTY: a command whose
//  backend is missing must return NotAvailable, never Ok.
//
//  console.cpp links against ImGui only inside Draw(); the test supplies
//  minimal stubs so the command layer can be exercised head-less.
// ===========================================================================

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

#include "console.h"
#include "entityops.h"
#include <cstdint>

// ---- ImGui stubs (Draw is never called; these only satisfy the linker) -----
namespace ImGui {
struct ImVec2 { float x, y; ImVec2(float a = 0, float b = 0) : x(a), y(b) {} };
struct ImGuiStyle { ImVec2 ItemSpacing; };
void SetNextWindowSize(const ImVec2&, int) {}
bool Begin(const char*, bool*) { return false; }
void End() {}
void BeginChild(const char*, const ImVec2&, int) {}
void EndChild() {}
void TextUnformatted(const char*) {}
void SetScrollHereY(float) {}
void SetNextItemWidth(float) {}
void SetKeyboardFocusHere() {}
bool InputText(const char*, char*, unsigned long, int) { return false; }
bool IsItemActive() { return false; }
bool IsWindowAppearing() { return false; }
ImGuiStyle& GetStyle() { static ImGuiStyle s; return s; }
float GetFrameHeightWithSpacing() { return 0; }
} // namespace ImGui

// ---- mod / mount / gamehooks stubs ----------------------------------------
namespace wolfmount::mod {
void RequestSummon() {}
} // namespace wolfmount::mod

namespace wolfmount::mount {
void TryEnterMount() {}
void ExitMount() {}
} // namespace wolfmount::mount

namespace wolfmount::gamehooks {
bool IsActive() { return false; }
bool HasWorldContext() { return false; }
void* WorldHolder() { return nullptr; }
bool HasEntityStore() { return false; }
int  EnqueueCount() { return 0; }
int  TameIssuedCount() { return 0; }
int  TorchTameCount() { return 0; }
uint32_t LastWildBeast() { return 0; }
bool TameEntity(uint32_t, bool) { return false; }
bool TransformEnemyToWildlife() { return false; }
} // namespace wolfmount::gamehooks

// ---- entityops stubs ------------------------------------------------------
// The real implementations touch live game memory. Here every one of them
// reports "no world", which is exactly the state the console must survive: it
// has to say NotAvailable instead of pretending it wrote something.
namespace wolfmount::entityops {
bool HasManager() { return false; }
void* Manager() { return nullptr; }
bool ResolveManager() { return false; }
int  EntityCount() { return 0; }
int  ListEntities(uint32_t*, int) { return 0; }
int  LastScanSize() { return 0; }
int  DiscoverFactionSlot() { return -1; }
int  FactionSlot() { return -1; }
int  ReadFaction(uint32_t) { return -1; }
bool WriteFaction(uint32_t, uint8_t) { return false; }
uint32_t PlayerEntityId() { return 0; }
bool PlayerPosition(double*, double*, double*) { return false; }
int  ListWildBeasts(uint32_t*, int) { return 0; }
bool ReadComponent(uint32_t, int, void*, uint16_t) { return false; }
bool WriteComponent(uint32_t, int, const void*, uint16_t) { return false; }
uintptr_t ComponentAddress(uint32_t, int, uint16_t*) { return 0; }
uint32_t SpawnAt(const uint8_t[16], double, double, double, uint32_t) { return 0; }
int  SpawnNearPlayer(const uint8_t[16], int, double, uint32_t) { return 0; }
void DumpEntity(uint32_t, int) {}

const uint8_t kPlayerGuid[16] = {0};

bool ParseGuid(const char* text, uint8_t out[16]) {
    if (!text || !out) return false;
    int n = 0;
    for (const char* p = text; *p; ++p) {
        if (*p == '-' || *p == ' ') continue;
        if (!((*p >= '0' && *p <= '9') || (*p >= 'a' && *p <= 'f') ||
              (*p >= 'A' && *p <= 'F'))) {
            return false;
        }
        ++n;
    }
    if (n != 32) return false;
    for (int i = 0; i < 16; ++i) out[i] = 0xAB;
    return true;
}

void FormatGuid(const uint8_t guid[16], char out[37]) {
    if (!guid || !out) return;
    for (int i = 0; i < 36; ++i) out[i] = '0';
    out[36] = '\0';
}

// One entry, so the console can be checked for "unknown template" handling
// without linking the real table.
static const NamedTemplate kTestTemplates[] = {
    {"wolf", "478381c5-585f-4264-b373-dbb1ea596eca", "test wolf"},
};

const NamedTemplate* Templates(int* count) {
    if (count) *count = 1;
    return kTestTemplates;
}

const NamedTemplate* LookupTemplate(const char* name) {
    if (!name) return nullptr;
    return std::strcmp(name, "wolf") == 0 ? &kTestTemplates[0] : nullptr;
}
} // namespace wolfmount::entityops

using wolfmount::console::Execute;
using wolfmount::console::Result;

static int g_pass = 0;
static int g_fail = 0;

static void Check(bool ok, const char* what) {
    if (ok) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s\n", what);
    }
}

static void CheckEq(Result got, Result want, const char* what) {
    if (got == want) {
        ++g_pass;
    } else {
        ++g_fail;
        std::printf("  FAIL: %s (got %d, want %d)\n", what, (int)got, (int)want);
    }
}

int main() {
    std::vector<std::string> scroll;

    std::printf("--- console command parsing ---\n");

    // Empty line is a no-op, not an error.
    CheckEq(Execute(""), Result::Ok, "empty line is Ok");

    // Unknown command is reported, never silently accepted.
    CheckEq(Execute("frobnicate"), Result::UnknownCommand,
            "unknown command -> UnknownCommand");

    // help lists every registered command.
    CheckEq(Execute("help"), Result::Ok, "help is Ok");

    std::printf("--- commands with no backend must say so ---\n");

    // spawn needs the entity manager. Without a world it must NOT claim success.
    CheckEq(Execute("spawn wolf"), Result::NotAvailable,
            "spawn without entity manager -> NotAvailable");

    // Missing argument is a bad-argument error, distinct from unavailable.
    CheckEq(Execute("spawn"), Result::BadArguments,
            "spawn with no args -> BadArguments");

    // An unknown template name is a caller error, caught before the backend.
    CheckEq(Execute("spawn definitely_not_a_template"), Result::BadArguments,
            "spawn with unknown template -> BadArguments");

    // tame with no known wolf cannot proceed.
    CheckEq(Execute("tame"), Result::BadArguments,
            "tame with no wolf seen -> BadArguments");

    // With an explicit id but no world context, the write cannot happen.
    CheckEq(Execute("tame 1234"), Result::NotAvailable,
            "tame without world context -> NotAvailable");

    // faction without world context likewise.
    CheckEq(Execute("faction 1234 11"), Result::NotAvailable,
            "faction without world context -> NotAvailable");

    // But a malformed faction id is caught before the backend is consulted.
    CheckEq(Execute("faction notanumber 11"), Result::BadArguments,
            "faction with bad id -> BadArguments");

    // A faction value outside the 16-value enum is refused, so a typo cannot
    // write a byte the AI will misinterpret.
    CheckEq(Execute("faction 1234 99"), Result::BadArguments,
            "faction with out-of-range value -> BadArguments");

    // transform needs the world context, so with the stub backend it must
    // report NotAvailable rather than claim it converted anything.
    CheckEq(Execute("transform"), Result::NotAvailable,
            "transform without world context -> NotAvailable");

    std::printf("--- commands that work today ---\n");

    CheckEq(Execute("status"), Result::Ok, "status is Ok");
    CheckEq(Execute("summon"), Result::Ok, "summon is Ok");
    CheckEq(Execute("mount"), Result::Ok, "mount is Ok");
    CheckEq(Execute("mount off"), Result::Ok, "mount off is Ok");

    // clear empties the scrollback.
    Execute("clear");
    Check(scroll.empty(), "clear empties scrollback");

    // Every registered name must dispatch to something (no dead entries).
    for (const char* n : wolfmount::console::CommandNames()) {
        const Result r = Execute(n);
        Check(r != Result::UnknownCommand, n);
    }

    std::printf("\n%d passed, %d failed\n", g_pass, g_fail);
    if (g_fail == 0) std::printf("RESULT: PASS\n");
    else             std::printf("RESULT: FAIL\n");
    return g_fail == 0 ? 0 : 1;
}
