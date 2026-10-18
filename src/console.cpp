// ============================================================================
//  WolfMount — in-game command console (command layer, no ImGui)
//
//  Each command below is wired to something the mod can actually do right now.
//  Where the engine has no reachable entry point, the command reports
//  `NotAvailable` with the concrete reason instead of pretending to work.
// ============================================================================

#include "console.h"

#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <sstream>

#include "gamehooks.h"
#include "entityops.h"
#include "faction.h"
#include "gamedata.h"
#include "mod.h"
#include "mount.h"
#include "tame.h"
#include <cstdint>

namespace wolfmount::console {
namespace {

void Format(std::string& out, const char* fmt, va_list ap) {
    char buf[1024];
    vsnprintf(buf, sizeof(buf), fmt, ap);
    out.append(buf);
}

// Append one line to the shared scrollback.
void Emit(const char* fmt, ...) {
    std::string s;
    va_list ap;
    va_start(ap, fmt);
    Format(s, fmt, ap);
    va_end(ap);

    auto& scroll = Scrollback();
    scroll.push_back(s);
    if (scroll.size() > 500) scroll.erase(scroll.begin());
}

std::vector<std::string> Tokenize(const std::string& line) {
    std::vector<std::string> out;
    std::istringstream is(line);
    std::string tok;
    while (is >> tok) out.push_back(tok);
    return out;
}

bool ParseU32(const std::string& s, uint32_t* out) {
    if (s.empty()) return false;
    char* end = nullptr;
    unsigned long v = strtoul(s.c_str(), &end, 0);
    if (!end || *end) return false;
    *out = static_cast<uint32_t>(v);
    return true;
}

// ---- individual commands ---------------------------------------------------

Result CmdStatus(const std::vector<std::string>&) {
    Emit("game hooks      : %s", gamehooks::IsActive() ? "active" : "inactive");
    Emit("world context   : %s", gamehooks::HasWorldContext() ? "acquired" : "waiting");
    Emit("world holder    : %s", gamehooks::WorldHolder() ? "captured" : "waiting");
    Emit("entity store    : %s", gamehooks::HasEntityStore() ? "accessible" : "not found");
    Emit("Enqueue calls   : %d", gamehooks::EnqueueCount());
    Emit("tame writes     : %d", gamehooks::TameIssuedCount());
    Emit("torch rule hits : %d", gamehooks::TorchTameCount());
    const uint32_t wolf = gamehooks::LastWildBeast();
    if (wolf) Emit("last wild wolf  : %u", wolf);
    else      Emit("last wild wolf  : (none seen)");

    // The memory-side entity backend: this is the path that actually writes
    // components now, so its state belongs in `status`.
    if (entityops::HasManager()) {
        Emit("entity manager  : %p (%d live)",
             entityops::Manager(), entityops::EntityCount());
        const int slot = entityops::FactionSlot();
        if (slot >= 0) Emit("faction slot    : %d", slot);
        else           Emit("faction slot    : (not identified yet)");
        const uint32_t pid = entityops::PlayerEntityId();
        if (pid) Emit("player entity   : %u", pid);
        else     Emit("player entity   : (not found)");
        double px = 0, py = 0, pz = 0;
        if (entityops::PlayerPosition(&px, &py, &pz)) {
            Emit("player position : %.1f, %.1f, %.1f", px, py, pz);
        }
        Emit("wild beasts     : %d live", entityops::ListWildBeasts(nullptr, 0));
    } else {
        Emit("entity manager  : (not resolved yet)");
    }
    return Result::Ok;
}

Result CmdFaction(const std::vector<std::string>& a) {
    if (a.size() < 2) {
        Emit("usage: faction <entityId> [value]");
        Emit("   known values: 6=WildBeast 7=Player 11=PlayerAlly 12=FarmAnimal");
        return Result::BadArguments;
    }
    uint32_t eid = 0;
    if (!ParseU32(a[1], &eid) || eid == 0) {
        Emit("faction: bad entity id '%s'", a[1].c_str());
        return Result::BadArguments;
    }

    // Validate the value BEFORE consulting the backend. A caller error must be
    // reported as a caller error even when the backend happens to be absent,
    // otherwise a typo looks like a capability gap.
    uint32_t val = 0;
    const bool haveValue = (a.size() >= 3);
    if (haveValue) {
        if (!ParseU32(a[2], &val) || val > 15) {
            Emit("faction: bad value '%s' (FactionType is 0..15)", a[2].c_str());
            return Result::BadArguments;
        }
    }

    // The manager must be live before we can read or write anything: the slot
    // address depends on the entity's own def/chunk/slot record.
    if (!entityops::ResolveManager()) {
        Emit("faction: entity manager not found yet (enter a world first)");
        return Result::NotAvailable;
    }
    if (entityops::DiscoverFactionSlot() < 0) {
        Emit("faction: Faction component slot not identified yet");
        Emit("         (needs a populated world to tell it apart by values)");
        return Result::NotAvailable;
    }

    if (!haveValue) {
        const int now = entityops::ReadFaction(eid);
        if (now < 0) {
            Emit("faction: entity %u not live (or has no Faction component)", eid);
            return Result::BadArguments;
        }
        Emit("faction: entity %u is %d (%s), slot %d", eid, now,
             game::FactionName(static_cast<uint8_t>(now)),
             entityops::FactionSlot());
        return Result::Ok;
    }

    const int before = entityops::ReadFaction(eid);
    if (before < 0) {
        Emit("faction: entity %u not live", eid);
        return Result::BadArguments;
    }

    // WriteFaction verifies by read-back, so a true here means the byte really
    // changed. That is the standard this command holds itself to: the old
    // Enqueue path reported success while writing nothing at all.
    if (!entityops::WriteFaction(eid, static_cast<uint8_t>(val))) {
        Emit("faction: WRITE FAILED for entity %u", eid);
        return Result::NotAvailable;
    }

    const int after = entityops::ReadFaction(eid);
    Emit("faction: %u  %d(%s) -> %d(%s)  VERIFIED by read-back", eid, before,
         game::FactionName(static_cast<uint8_t>(before)), after,
         game::FactionName(static_cast<uint8_t>(after)));
    if (after == static_cast<int>(val) && val == 11) {
        Emit("         PlayerAlly (11): the engine's own isEnemy() treats this as");
        Emit("         friendly to the player, so the wolf should stop attacking.");
    }
    return Result::Ok;
}

Result CmdTame(const std::vector<std::string>& a) {
    uint32_t eid = 0;
    if (a.size() >= 2) {
        if (!ParseU32(a[1], &eid)) {
            Emit("tame: bad entity id '%s'", a[1].c_str());
            return Result::BadArguments;
        }
    } else {
        // Pick the nearest wolf by faction rather than the last one hit.
        static uint32_t ids[64];
        const int n = entityops::ListWildBeasts(ids, 64);
        if (n <= 0) {
            Emit("tame: no WildBeast entity is live right now");
            return Result::BadArguments;
        }
        eid = ids[0];
        Emit("tame: chose WildBeast entity %u (of %d live)", eid, n);
    }

    if (entityops::ResolveManager() && entityops::DiscoverFactionSlot() >= 0) {
        const int before = entityops::ReadFaction(eid);
        if (before < 0) {
            Emit("tame: entity %u not live", eid);
            return Result::BadArguments;
        }
        // A wolf is a plain Enemy unit: it carries no Animal/Wildlife component,
        // so the engine's taming pipeline has nothing to act on. What makes a
        // wolf behave as an ally is its Faction byte, not IsTame.
        if (!entityops::WriteFaction(eid, faction::kPlayerAlly)) {
            Emit("tame: faction write FAILED for entity %u", eid);
            return Result::NotAvailable;
        }
        const int after = entityops::ReadFaction(eid);
        Emit("tame: entity %u  %d(%s) -> %d(%s)  VERIFIED",
             eid, before, game::FactionName(static_cast<uint8_t>(before)),
             after, game::FactionName(static_cast<uint8_t>(after)));
        Emit("      Faction is what the AI actually reads; IsTame on a wolf has");
        Emit("      no consumer (verified: wolves carry no Animal component).");

        // Faction alone stops it attacking us and starts it attacking everyone
        // else -- that is IsEnemy's default branch doing the work. It does NOT
        // make it follow: this engine has no follow behaviour to enable (see
        // docs/TECHNIQUE.md §6a), so enrol it in our own follow loop instead.
        if (entityops::FollowAdd(eid)) {
            Emit("      enrolled as a follower (%d in the set); it will trail you",
                 entityops::FollowCount());
        } else {
            Emit("      could NOT enrol it as a follower (set full)");
        }
        return Result::Ok;
    }

    return Result::NotAvailable;
}

Result CmdSpawn(const std::vector<std::string>& a) {
    int count = 0;
    const entityops::NamedTemplate* all = entityops::Templates(&count);

    if (a.size() < 2) {
        Emit("usage: spawn <template> [count] [distance]");
        Emit("   templates:");
        for (int i = 0; i < count; ++i) {
            Emit("     %-11s %s", all[i].name, all[i].note);
        }
        Emit("   a 32-digit hex GUID is also accepted");
        return Result::BadArguments;
    }

    // Accept a table name or a raw GUID.
    uint8_t guid[16] = {0};
    const entityops::NamedTemplate* named = entityops::LookupTemplate(a[1].c_str());
    if (named) {
        if (!entityops::ParseGuid(named->guid, guid)) {
            Emit("spawn: table entry '%s' has an unparseable GUID", named->name);
            return Result::BadArguments;
        }
    } else if (!entityops::ParseGuid(a[1].c_str(), guid)) {
        Emit("spawn: '%s' is not a known template name or a 16-byte GUID",
             a[1].c_str());
        Emit("       run `spawn` with no arguments to list the known names");
        return Result::BadArguments;
    }

    int want = 1;
    if (a.size() >= 3) {
        uint32_t v = 0;
        if (!ParseU32(a[2], &v) || v == 0 || v > 8) {
            Emit("spawn: count must be 1..8");
            return Result::BadArguments;
        }
        want = static_cast<int>(v);
    }

    double dist = 3.0;
    if (a.size() >= 4) {
        char* end = nullptr;
        const double v = strtod(a[3].c_str(), &end);
        if (!end || *end || v < 0.5 || v > 30.0) {
            Emit("spawn: distance must be 0.5..30");
            return Result::BadArguments;
        }
        dist = v;
    }

    if (!entityops::ResolveManager()) {
        Emit("spawn: entity manager not found yet — enter a world first");
        return Result::NotAvailable;
    }

    char pretty[37];
    entityops::FormatGuid(guid, pretty);
    const int made = entityops::SpawnNearPlayer(guid, want, dist, 1);
    if (made <= 0) {
        Emit("spawn: asked for %d, but the factory produced no live entity", want);
        Emit("        (see the log: the create call may have been refused)");
        return Result::NotAvailable;
    }
    Emit("spawn: %d live entit%s from %s", made, made == 1 ? "y" : "ies", pretty);
    if (named) Emit("       template %s", named->name);
    // Do not let the user believe the requested distance is guaranteed. The
    // factory (rva 0x97B790) ignores desc+0x18 and therefore ignores any
    // position we hand it; the entity first appears wherever the template says
    // and is then moved. If that move fails the template position stands.
    Emit("       position: moved to ~%.1f m from you AFTER spawning", dist);
    Emit("       (the factory ignores the position we pass, so the template's");
    Emit("        own position is the fallback if the move does not stick)");
    return Result::Ok;
}

Result CmdTransform(const std::vector<std::string>&) {
    if (!gamehooks::HasWorldContext()) {
        Emit("transform: world context not acquired yet (enter a world)");
        return Result::NotAvailable;
    }
    // Verified crash (2026-10-18): calling wildlife_enemy_transformer from the
    // render thread faults the game at rva 0x9B8013, because the 0xa8-byte
    // query object it builds is only valid while the engine's own dispatcher
    // drives the handler. The command stays registered so the failure is
    // explicit rather than a silent no-op.
    Emit("transform: REFUSED - this crashes the game.");
    Emit("          The engine's wildlife_enemy_transformer (rva 0x480C70) may");
    Emit("          only be invoked by the game's own program dispatcher;");
    Emit("          calling it directly faults at rva 0x9B8013");
    Emit("          (movq 0x58(%rax),%rcx with a garbage world pointer).");
    Emit("          Next step: hook the dispatcher that walks world+0x746350");
    Emit("          (stride 0x1f20) and calls slot+0x28.");
    return Result::NotAvailable;
}

Result CmdSummon(const std::vector<std::string>&) {
    mod::RequestSummon();
    Emit("summon: request dispatched to the mod's summon path");
    return Result::Ok;
}

Result CmdMount(const std::vector<std::string>& a) {
    if (a.size() >= 2 && a[1] == "off") {
        mount::ExitMount();
        Emit("mount: exited");
    } else {
        mount::TryEnterMount();
        Emit("mount: entered (local state machine only; no engine attachment yet)");
    }
    return Result::Ok;
}

Result CmdHelp(const std::vector<std::string>&);

Result CmdPos(const std::vector<std::string>&) {
    if (!entityops::HasManager()) {
        Emit("pos: entity manager not found — enter a world first");
        return Result::NotAvailable;
    }
    if (entityops::FactionSlot() < 0) {
        Emit("pos: faction slot not identified yet");
        return Result::NotAvailable;
    }
    // The dump goes to the log; echo the human-readable part here too.
    entityops::DumpPlayerPosition();

    const uint32_t pid = entityops::PlayerEntityId();
    double px = 0, py = 0, pz = 0;
    const bool ok = entityops::PlayerPosition(&px, &py, &pz);
    Emit("pos: player entity = %u", pid);
    if (ok) Emit("pos: player position = %.2f, %.2f, %.2f", px, py, pz);
    else    Emit("pos: player position = UNAVAILABLE");
    Emit("pos: details for every Faction==Player entity are in the log");
    return Result::Ok;
}

struct Command {
    const char* name;
    const char* help;
    Result (*fn)(const std::vector<std::string>&);
};

const Command kCommands[] = {
    {"status",  "show hook/context/write counters",                    CmdStatus},
    {"tame",    "tame [entityId] — write IsTame via the game's writer", CmdTame},
    {"faction", "faction <entityId> [value] — set Faction",             CmdFaction},
    {"spawn",   "spawn <template> — request a spawn (backend pending)",  CmdSpawn},
    {"summon",  "summon — call the mod's own summon path",              CmdSummon},
    {"pos",     "pos — diagnose why the player position is (un)readable", CmdPos},
    {"transform","transform — run the engine's enemy->wildlife program", CmdTransform},
    {"mount",   "mount [off] — toggle the mount state machine",         CmdMount},
    {"help",    "help — list commands",                                 CmdHelp},
    {"clear",   "clear — empty the scrollback",                         nullptr},
};

Result CmdHelp(const std::vector<std::string>&) {
    Emit("commands:");
    for (const auto& c : kCommands) Emit("  %-9s %s", c.name, c.help);
    return Result::Ok;
}

} // namespace

std::vector<std::string>& Scrollback() {
    static std::vector<std::string> s;
    return s;
}

const std::vector<const char*>& CommandNames() {
    static std::vector<const char*> names = [] {
        std::vector<const char*> v;
        for (const auto& c : kCommands) v.push_back(c.name);
        return v;
    }();
    return names;
}

bool IsCommand(const char* name) {
    if (!name) return false;
    for (const auto& c : kCommands) {
        if (std::strcmp(name, c.name) == 0) return true;
    }
    return false;
}

Result Execute(const std::string& line) {
    const auto args = Tokenize(line);
    if (args.empty()) return Result::Ok;

    const std::string& cmd = args[0];

    if (cmd == "clear") {
        Scrollback().clear();
        return Result::Ok;
    }

    for (const auto& c : kCommands) {
        if (cmd == c.name) {
            if (!c.fn) return Result::Ok;
            return c.fn(args);
        }
    }

    Emit("unknown command: %s  (try `help`)", cmd.c_str());
    return Result::UnknownCommand;
}

} // namespace wolfmount::console
