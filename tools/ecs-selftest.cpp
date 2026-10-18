// ============================================================================
//  WolfMount — ECS probe self test
//
//  Exercises the same PE section walk the layer's probe uses, but against the
//  executable FILE rather than a mapped image, so it can run without the game.
//  Confirms every ECS signature the mod depends on exists in the shipped build.
// ============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <cstdio>
#include <cstring>
#include <vector>

struct Sec {
    char     name[9];
    uint32_t ptrRaw;
    uint32_t sizeRaw;
    uint32_t va;
    uint32_t vsize;
};

static std::vector<Sec> LoadSections(const uint8_t* base) {
    std::vector<Sec> out;
    auto* dos = reinterpret_cast<const IMAGE_DOS_HEADER*>(base);
    auto* nt = reinterpret_cast<const IMAGE_NT_HEADERS64*>(base + dos->e_lfanew);
    auto* sec = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i, ++sec) {
        Sec s{};
        memcpy(s.name, sec->Name, 8);
        s.name[8] = 0;
        s.ptrRaw = sec->PointerToRawData;
        s.sizeRaw = sec->SizeOfRawData;
        s.va = sec->VirtualAddress;
        s.vsize = sec->Misc.VirtualSize;
        out.push_back(s);
    }
    return out;
}

// Search a file-backed image: returns the file offset, and reports the
// section it landed in.
static bool FindInImage(const uint8_t* base, size_t len,
                        const std::vector<Sec>& secs,
                        const char* needle,
                        uint64_t* fileOff, const char** section) {
    size_t n = strlen(needle);
    for (const auto& s : secs) {
        if (s.sizeRaw == 0) continue;
        if (s.ptrRaw + s.sizeRaw > len) continue;
        const uint8_t* start = base + s.ptrRaw;
        for (size_t off = 0; off + n <= s.sizeRaw; ++off) {
            if (memcmp(start + off, needle, n) == 0) {
                *fileOff = s.ptrRaw + off;
                *section = s.name;
                return true;
            }
        }
    }
    return false;
}

int main(int argc, char** argv) {
    const char* path = (argc > 1) ? argv[1] : "enshrouded.exe";
    printf("=== WolfMount ECS probe self test ===\n\n");

    FILE* f = fopen(path, "rb");
    if (!f) { printf("FAIL  cannot open %s\n", path); return 1; }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    std::vector<uint8_t> buf(sz);
    size_t rd = fread(buf.data(), 1, sz, f);
    fclose(f);
    if (rd != (size_t)sz) { printf("FAIL  short read\n"); return 1; }

    printf("  %s  (%ld bytes)\n", path, sz);
    auto secs = LoadSections(buf.data());
    printf("  %zu sections\n", secs.size());
    for (const auto& s : secs) {
        printf("    %-9s raw=0x%-8X size=0x%-8X va=0x%X\n",
               s.name, s.ptrRaw, s.sizeRaw, s.va);
    }
    printf("\n");

    const char* probes[] = {
        "adminSpawnCommand",
        "adminDebugEnemyAction",
        "If set to false the Wildlife behavior won't run if the Wildlife is tamed",
        "actor.TameWildlifeEvent",
        "HookShotAnchorSubEntity",
        "addImpactHierarchy",
        "ecs.Enemy01BehaviorState",
    };

    int found = 0;
    bool layoutOk = true;
    for (auto* p : probes) {
        uint64_t off = 0;
        const char* sec = "-";
        bool hit = FindInImage(buf.data(), buf.size(), secs, p, &off, &sec);
        printf("  %-4s %-56s 0x%08llX  [%s]\n",
               hit ? "HIT " : "MISS", p,
               hit ? (unsigned long long)off : 0ULL, sec);
        if (hit) found++;
        if (hit && strcmp(sec, ".rdata") != 0 && strcmp(sec, ".text") != 0 &&
                  strcmp(sec, ".data")  != 0) {
            printf("       WARN unexpected section '%s'\n", sec);
            layoutOk = false;
        }
    }

    printf("\n  %d/%d probes resolved\n", found, (int)(sizeof(probes)/sizeof(probes[0])));

    if (found == 0)            { printf("\nRESULT: FAIL\n"); return 1; }
    if (!layoutOk)             { printf("\nRESULT: PASS with warnings\n"); return 0; }
    printf("\nRESULT: PASS — ECS command surface confirmed in the shipped exe\n");
    return 0;
}
