// ===========================================================================
//  entityops-test.cpp — WolfMount entity backend unit test
//
//  Only the pure parts are exercised here: GUID parsing/formatting and the
//  template table. Everything else in entityops.cpp dereferences live game
//  memory, which a head-less test must never do.
//
//  The GUID contract is worth a test because the whole spawn path depends on it
//  and it was established by cross-check: `1_Player`'s TemplateResource filename
//  UUID and the kPlayerGuid baked into entityops.cpp are byte-identical.
// ===========================================================================

#include <cstdio>
#include <cstring>

#include "entityops.h"
#include <cstdint>

using namespace wolfmount;

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

int main() {
    std::printf("--- GUID parsing ---\n");

    // The dashed form, as it appears in TemplateResource filenames.
    uint8_t g[16];
    Check(entityops::ParseGuid("478381c5-585f-4264-b373-dbb1ea596eca", g),
          "dashed GUID parses");
    Check(g[0] == 0x47 && g[1] == 0x83 && g[2] == 0x81 && g[3] == 0xC5,
          "first four bytes are in printed order");
    Check(g[15] == 0xCA, "last byte is the final hex pair");

    // The undashed form must produce identical bytes: callers paste both.
    uint8_t g2[16];
    Check(entityops::ParseGuid("478381c5585f4264b373dbb1ea596eca", g2),
          "undashed GUID parses");
    Check(std::memcmp(g, g2, 16) == 0, "dashed and undashed agree");

    // Upper case is accepted, because a human may type it.
    uint8_t g3[16];
    Check(entityops::ParseGuid("478381C5-585F-4264-B373-DBB1EA596ECA", g3),
          "upper-case GUID parses");
    Check(std::memcmp(g, g3, 16) == 0, "case does not change the bytes");

    std::printf("--- GUID parsing rejects bad input ---\n");

    Check(!entityops::ParseGuid("", g), "empty string rejected");
    Check(!entityops::ParseGuid(nullptr, g), "null rejected");
    Check(!entityops::ParseGuid("478381c5-585f-4264-b373", g),
          "too short rejected");
    Check(!entityops::ParseGuid(
              "478381c5-585f-4264-b373-dbb1ea596eca00", g),
          "too long rejected");
    Check(!entityops::ParseGuid("zzzzzzzz-585f-4264-b373-dbb1ea596eca", g),
          "non-hex rejected");
    Check(!entityops::ParseGuid("478381c5-585f-4264-b373-dbb1ea596ec", g),
          "one digit short rejected");

    std::printf("--- GUID formatting is the inverse ---\n");

    char text[37];
    entityops::FormatGuid(g, text);
    Check(std::strcmp(text, "478381c5-585f-4264-b373-dbb1ea596eca") == 0,
          "format restores the canonical dashed form");

    uint8_t round[16];
    Check(entityops::ParseGuid(text, round) && std::memcmp(g, round, 16) == 0,
          "format -> parse round-trips");

    // An all-zero GUID is the one value that must round-trip too, because a
    // failed spawn reports zero and the logging path still formats it.
    const uint8_t zero[16] = {0};
    entityops::FormatGuid(zero, text);
    Check(std::strcmp(text, "00000000-0000-0000-0000-000000000000") == 0,
          "zero GUID formats");

    std::printf("--- the player GUID matches its template file ---\n");

    // kPlayerGuid is the cross-check that established the byte order: it must
    // equal the UUID of TemplateResource's "1_Player" file.
    char player[37];
    entityops::FormatGuid(entityops::kPlayerGuid, player);
    Check(std::strcmp(player, "c3db66d6-89a5-4a6c-a8e3-d9a1f6009812") == 0,
          "kPlayerGuid is the 1_Player template UUID");

    std::printf("--- template table ---\n");

    int count = 0;
    const entityops::NamedTemplate* all = entityops::Templates(&count);
    Check(all != nullptr && count > 0, "template table is non-empty");

    bool allParse = true;
    bool allNamed = true;
    for (int i = 0; i < count; ++i) {
        uint8_t tmp[16];
        if (!entityops::ParseGuid(all[i].guid, tmp)) allParse = false;
        if (!all[i].name || !*all[i].name) allNamed = false;
    }
    Check(allParse, "every table GUID parses");
    Check(allNamed, "every table entry has a name");

    const entityops::NamedTemplate* wolf = entityops::LookupTemplate("wolf");
    Check(wolf != nullptr, "the wolf template is in the table");
    if (wolf) {
        Check(std::strcmp(wolf->guid,
                          "478381c5-585f-4264-b373-dbb1ea596eca") == 0,
              "wolf maps to Enemy_Wildbeast_wolf_earlygame");
    }

    Check(entityops::LookupTemplate("nope") == nullptr,
          "unknown name returns null");
    Check(entityops::LookupTemplate(nullptr) == nullptr,
          "null name returns null");

    std::printf("\n%d passed, %d failed\n", g_pass, g_fail);
    if (g_fail == 0) std::printf("RESULT: PASS\n");
    else             std::printf("RESULT: FAIL\n");
    return g_fail == 0 ? 0 : 1;
}
