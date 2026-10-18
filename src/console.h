#pragma once
// ============================================================================
//  WolfMount — in-game command console (head-less command layer)
//
//  WHAT THIS IS
//    The command parser and dispatcher. It deliberately has NO ImGui
//    dependency, so the whole command set can be unit-tested without a
//    renderer (see tools/console-test.cpp). The drawing lives in console_ui.cpp.
//
//  WHAT THE COMMANDS CAN AND CANNOT DO
//    The game has no reachable developer console. Its admin surface is a set of
//    *serialized action types* (keen::ecs::AdminSpawnCommand and friends); the
//    registry at 0x141507400 only describes their wire layout, and no code in
//    the binary reads that table. So a command typed here always reaches the
//    mod, but whether the engine acts on it depends on a dispatch backend that
//    is still being located.
//
//    Commands therefore report `NotAvailable` when the backend is missing
//    rather than pretending to succeed — a console that silently no-ops is
//    worse than no console.
// ============================================================================

#include <string>
#include <vector>

namespace wolfmount::console {

enum class Result {
    Ok,
    UnknownCommand,
    BadArguments,
    NotAvailable,   // command understood, backend missing
};

// The scrollback shared by Execute() and the UI.
std::vector<std::string>& Scrollback();

// Execute one line, appending output to the scrollback.
Result Execute(const std::string& line);

// Command names, for `help` and for completion.
const std::vector<const char*>& CommandNames();

// True when a command with this name exists.
bool IsCommand(const char* name);

} // namespace wolfmount::console
