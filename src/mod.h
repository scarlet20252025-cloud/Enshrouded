#pragma once
// ============================================================================
//  WolfMount — mod logic interface
//
//  Everything the player-visible mod does lives behind this interface so the
//  Vulkan layer stays a thin, testable shell.
// ============================================================================

#include <windows.h>
#include <cstdint>

namespace wolfmount::mod {

// ---- lifecycle -------------------------------------------------------------
void OnOverlayReady();

// ---- input -----------------------------------------------------------------
// Returns true if the message was consumed by the mod.
bool OnWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam);

// Polled input, called once per rendered frame.
//
// The game does NOT forward WM_KEYDOWN to the window procedure, so a
// message-driven hotkey never fires during normal play. Reading the key state
// directly with GetAsyncKeyState works regardless.
void PollInput();

// ---- rendering -------------------------------------------------------------
void DrawMenu();

// Draws the command console window. Independent of DrawMenu so the F9 console
// works while playing, with the F8 menu closed.
void DrawConsole();

// True while either the menu or the console window is visible.
bool IsAnyWindowOpen();

// ---- settings persistence --------------------------------------------------
void LoadSettings();
void SaveSettings();

// ---- summon (M2) -----------------------------------------------------------
// Bound to the summon key. Reports what it did through the returned state.
void RequestSummon();

// ---- diagnostics -----------------------------------------------------------
// A short, human readable description of the current runtime capability.
const char* RuntimeStatus();

// True while the mod menu panel is visible. The layer uses this to decide
// whether it needs to draw a software cursor.
bool IsMenuOpen();// ---- settings (read by the menu) ------------------------------------------
struct Settings {
    int  summonKey = 'Y';      // default summon key
    int  menuKey   = VK_F8;    // open/close the mod menu
    int  consoleKey = VK_F9;   // open/close the command console
    bool mountEnabled = true;
    bool combatFollowEnabled = true;
    bool tameOnTorchKill = true;
    int  maxWolves = 1;        // only one wolf may ever be tamed
    bool showDebug = false;
};

Settings& GetSettings();

} // namespace wolfmount::mod
