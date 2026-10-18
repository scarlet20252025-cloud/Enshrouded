// ============================================================================
//  WolfMount mod logic
//
//  M1 scope: settings, key handling, ImGui menu.
//  M2+ adds: AdminSpawnCommand summon, torch-kill taming, faction rewrite,
//            ImpactHierarchy mounting.
// ============================================================================

#include "mod.h"
#include "console_ui.h"
#include "ecs.h"
#include "entityops.h"
#include "follow.h"
#include "gamehooks.h"
#include "logging.h"
#include "mount.h"
#include "tame.h"

#include "imgui.h"

#include <atomic>
#include <cstdio>
#include <fstream>
#include <string>
#include <cstdint>

namespace wolfmount::mod {

// ---------------------------------------------------------------------------
//  Settings + persistence
// ---------------------------------------------------------------------------
static Settings g_settings;
static bool g_menuOpen = false;
static bool g_consoleOpen = false;

// Summon bookkeeping. A summon is only issued once the ECS probe has confirmed
// the command surface exists, so the menu can distinguish "not ready" from
// "summoned".
static int         g_summonCount = 0;
static const char* g_lastAction = "idle";

Settings& GetSettings() { return g_settings; }

static std::string SettingsPath() {
    char path[MAX_PATH] = {0};
    HMODULE h = nullptr;
    GetModuleHandleExA(
        GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS |
        GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
        (LPCSTR)&SettingsPath, &h);
    GetModuleFileNameA(h, path, MAX_PATH);
    return std::string(path) + ".settings.json";
}

void LoadSettings() {
    std::ifstream f(SettingsPath());
    if (!f) return;

    std::string line;
    while (std::getline(f, line)) {
        auto eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string k = line.substr(0, eq);
        std::string v = line.substr(eq + 1);

        if      (k == "summonKey")  g_settings.summonKey = std::stoi(v);
        else if (k == "menuKey")    g_settings.menuKey   = std::stoi(v);
        else if (k == "consoleKey") g_settings.consoleKey = std::stoi(v);
        else if (k == "mountEnabled")       g_settings.mountEnabled = (v == "1");
        else if (k == "combatFollowEnabled")g_settings.combatFollowEnabled = (v == "1");
        else if (k == "tameOnTorchKill")    g_settings.tameOnTorchKill = (v == "1");
        else if (k == "maxWolves")          g_settings.maxWolves = std::stoi(v);
        else if (k == "showDebug")          g_settings.showDebug = (v == "1");
    }
}

void SaveSettings() {
    std::ofstream f(SettingsPath(), std::ios::trunc);
    if (!f) return;

    f << "summonKey="   << g_settings.summonKey  << "\n";
    f << "menuKey="     << g_settings.menuKey    << "\n";
    f << "consoleKey="  << g_settings.consoleKey << "\n";
    f << "mountEnabled=" << (g_settings.mountEnabled ? 1 : 0) << "\n";
    f << "combatFollowEnabled=" << (g_settings.combatFollowEnabled ? 1 : 0) << "\n";
    f << "tameOnTorchKill=" << (g_settings.tameOnTorchKill ? 1 : 0) << "\n";
    f << "maxWolves="   << g_settings.maxWolves  << "\n";
    f << "showDebug="   << (g_settings.showDebug ? 1 : 0) << "\n";
}

// ---------------------------------------------------------------------------
//  Key name helper - renders a VK code as something readable in the menu.
// ---------------------------------------------------------------------------
static const char* KeyName(int vk) {
    static char buf[32];
    if (vk >= 'A' && vk <= 'Z') { buf[0] = (char)vk; buf[1] = 0; return buf; }
    if (vk >= '0' && vk <= '9') { buf[0] = (char)vk; buf[1] = 0; return buf; }
    switch (vk) {
        case VK_F1:  return "F1";
        case VK_F2:  return "F2";
        case VK_F3:  return "F3";
        case VK_F4:  return "F4";
        case VK_F5:  return "F5";
        case VK_F6:  return "F6";
        case VK_F7:  return "F7";
        case VK_F8:  return "F8";
        case VK_F9:  return "F9";
        case VK_F10: return "F10";
        case VK_F11: return "F11";
        case VK_F12: return "F12";
        case VK_SPACE:  return "Space";
        case VK_TAB:    return "Tab";
        case VK_SHIFT:  return "Shift";
        case VK_CONTROL:return "Ctrl";
        case VK_MENU:   return "Alt";
        case 'E':       return "E";
        default:        snprintf(buf, sizeof(buf), "VK_%02X", vk); return buf;
    }
}

// ---------------------------------------------------------------------------
//  Lifecycle
// ---------------------------------------------------------------------------
void OnOverlayReady() {
    LoadSettings();
    g_menuOpen = false;
    g_consoleOpen = false;

    // Probe the ECS command surface now that we are inside the game process.
    const auto& probe = wolfmount::ecs::Probe();
    g_lastAction = probe.status;

    // Install the game hooks (M3/M6). This verifies the death-site bytes and
    // reports success/failure so the menu can show the real runtime state.
    int hooked = wolfmount::gamehooks::Install();
    if (hooked > 0) {
        WM_MOD_LOG("[wolfmount] game hooks installed: %d", hooked);
        g_lastAction = "game hooks installed";
    } else {
        WM_MOD_LOG("[wolfmount] game hooks NOT installed (game updated?)");
        g_lastAction = "game hooks unavailable";
    }
}

// ---------------------------------------------------------------------------
//  Input - polled
//
//  WHY POLLING IS REQUIRED
//
//  The game does not deliver WM_KEYDOWN to its window procedure: a message
//  trace covering a full session showed mouse messages arriving but not a
//  single key message, because the game reads the keyboard through raw input
//  and never dispatches key messages to the window.
//
//  That means a hotkey implemented only in the WndProc never fires during
//  normal play. GetAsyncKeyState reads the hardware state regardless of who
//  consumes the messages, so polling once per frame is reliable.
//
//  Edge detection: we act on the transition from "up" to "down" only, so
//  holding a key does not repeat the action.
// ---------------------------------------------------------------------------
static bool KeyWentDown(int vk, bool& wasDown) {
    // The 0x8000 bit is "currently down"; the 0x0001 bit is "pressed since the
    // last call", which is not reliable when the game also polls.
    bool down = (GetAsyncKeyState(vk) & 0x8000) != 0;
    bool edge = down && !wasDown;
    wasDown = down;
    return edge;
}

void PollInput() {
    static bool menuWasDown   = false;
    static bool summonWasDown = false;
    static bool consoleWasDown = false;
    static int  diagFrames    = 0;

    // Low-frequency diagnostic: confirms the poll runs at all and shows what
    // GetAsyncKeyState actually reports for the bound keys. Cheap (a few times
    // per session) and decisive when a hotkey appears dead.
    if (diagFrames < 3 && (diagFrames++ % 1200) == 0) {
        WM_MOD_LOG("[wolfmount] poll diag: menuKey=%d(0x%X) state=0x%04X  "
                   "summonKey=%d(0x%X) state=0x%04X  consoleKey=%d(0x%X) "
                   "state=0x%04X",
                   g_settings.menuKey, g_settings.menuKey,
                   (unsigned)(GetAsyncKeyState(g_settings.menuKey) & 0xFFFF),
                   g_settings.summonKey, g_settings.summonKey,
                   (unsigned)(GetAsyncKeyState(g_settings.summonKey) & 0xFFFF),
                   g_settings.consoleKey, g_settings.consoleKey,
                   (unsigned)(GetAsyncKeyState(g_settings.consoleKey) & 0xFFFF));
    }

    // The menu key must work whether the panel is open or closed.
    if (KeyWentDown(g_settings.menuKey, menuWasDown)) {
        g_menuOpen = !g_menuOpen;
        g_lastAction = g_menuOpen ? "menu opened" : "menu closed";
        WM_MOD_LOG("[wolfmount] menu %s (polled)", g_menuOpen ? "opened" : "closed");
        // Opening the menu must never be blocked by a console sitting on top of
        // it, so the console steps aside whenever the menu takes over.
        if (g_menuOpen && g_consoleOpen) {
            g_consoleOpen = false;
            WM_MOD_LOG("[wolfmount] console closed (menu took over)");
        }
    }

    // Console toggle - a second, independent window so it can stay open while
    // playing. Suppressed while the console text field has focus, so typing a
    // key that happens to be the toggle does not close it mid-word.
    //
    // The console key is checked FIRST and unconditionally (only the text-field
    // guard applies), because it is the escape hatch when the console itself
    // has gone wrong. If the console is stuck open with keyboard focus, this is
    // still the only way back — the menu key would be swallowed by the field.
    if (!wolfmount::console::ui::WantsKeyboard() &&
        KeyWentDown(g_settings.consoleKey, consoleWasDown)) {
        g_consoleOpen = !g_consoleOpen;
        g_lastAction = g_consoleOpen ? "console opened" : "console closed";
        WM_MOD_LOG("[wolfmount] console %s (polled)",
                   g_consoleOpen ? "opened" : "closed");
        // Same rule in the other direction: a console opened while the menu is
        // up would cover the menu's buttons, so the menu closes instead.
        if (g_consoleOpen && g_menuOpen) {
            g_menuOpen = false;
            WM_MOD_LOG("[wolfmount] menu closed (console took over)");
        }
    }

    // The summon key is only meaningful while no text field is capturing input,
    // so it does not fight with typing in the menu or console.
    const bool typing = g_menuOpen || wolfmount::console::ui::WantsKeyboard();
    if (!typing && KeyWentDown(g_settings.summonKey, summonWasDown)) {
        RequestSummon();
    } else if (typing) {
        // Keep the edge state fresh so closing the menu does not immediately
        // fire a summon from a key held during the menu.
        (void)KeyWentDown(g_settings.summonKey, summonWasDown);
    }

    // -------------------------------------------------------------------------
    //  Entity pipeline
    //
    //  Three stages, each gated on the previous one having produced something
    //  real. Every stage logs once when it completes, so a run's log says how
    //  far the pipeline got without anyone having to open the console.
    //
    //      1. resolve manager      needs a loaded world
    //      2. discover faction     needs a populated entity table (>=32)
    //      3. snapshot             needs the faction slot
    //
    //  Caution: probing is read-guarded and bounded, but it is not free, so each
    //  stage retries on a slow cadence rather than every frame.
    // -------------------------------------------------------------------------
    static int entityProbeFrames = 0;
    static bool snapshotDone = false;
    ++entityProbeFrames;

    if (!entityops::HasManager()) {
        if ((entityProbeFrames % 120) == 0) {
            entityops::ResolveManager();
        }
    } else if (entityops::FactionSlot() < 0) {
        // Faction discovery is expensive (entities x 640 slot reads), so on
        // failure back off exponentially instead of retrying forever at a fixed
        // cadence. Two failed attempts are already enough to know the shape
        // test needs changing; hammering it just costs frames.
        static int factionAttempts = 0;
        static int factionCooldown = 240;
        static int factionFrames = 0;
        ++factionFrames;
        if (factionAttempts < 4 && factionFrames >= factionCooldown &&
            entityops::EntityCount() >= 32) {
            factionFrames = 0;
            ++factionAttempts;
            factionCooldown = 240 * (factionAttempts + 1);
            entityops::DiscoverFactionSlot();
        }
    } else if (!snapshotDone && (entityProbeFrames % 300) == 0) {
        // Stage 3. This is read-only: it proves the faction slot is usable for
        // reading before anything tries to write through it, and it records the
        // one thing that is otherwise invisible -- whether the player and any
        // wild beasts are visible through the discovered slot.
        snapshotDone = entityops::LogEntitySnapshot();
    }

    // Stage 4: the follow loop.
    //
    // This engine has no follow behaviour to enable (see entityops.h), so a
    // companion is moved by us. That makes this the one part of the mod that
    // runs every frame, so it is written to cost nothing when there is nothing
    // to do: it returns immediately unless a world, a player position and at
    // least one live follower are all known.
    //
    // 8 m behind and a 40 m teleport threshold are chosen so a companion keeps
    // up at walking pace but appears next to the player after a glide or a fast
    // travel instead of hiking across the map.
    if (entityops::FollowCount() > 0) {
        entityops::FollowTick(8.0, 40.0);
    }

    // Stage 5: the mount. While riding, the player's transform is copied from
    // the wolf's every frame. This is a no-op unless something is actually
    // mounted, so it costs one atomic load on the overwhelming majority of
    // frames.
    entityops::MountTick();
}

// ---------------------------------------------------------------------------
//  Input - window messages
//
//  The layer forwards every window message here AFTER giving it to ImGui, so
//  the UI already has up-to-date mouse and keyboard state. This function only
//  decides whether the GAME should also see it.
//
//  Returning true means "the mod consumed this message".
//
//  While the menu is open we consume all mouse and keyboard input, otherwise
//  clicking a checkbox would also swing the player's camera or attack. When
//  the menu is closed we consume nothing except the menu key itself.
//
//  Note: the menu toggle is NOT handled here - see PollInput. Key messages do
//  not reach this window in practice.
// ---------------------------------------------------------------------------
bool OnWndProc(HWND hWnd, UINT msg, WPARAM wParam, LPARAM lParam) {
    (void)hWnd;

    switch (msg) {
        case WM_KEYDOWN:
        case WM_SYSKEYDOWN: {
            // Key messages are rare here (see PollInput), but if the game ever
            // does deliver one while a panel is open, keep it from the game.
            if (IsAnyWindowOpen()) return true;
            return false;
        }

        case WM_KEYUP:
        case WM_SYSKEYUP:
        case WM_CHAR:
            // Swallow key releases only while a panel owns the keyboard, so a
            // key held when the panel opened does not stick in the game.
            return IsAnyWindowOpen();

        // ---- mouse ---------------------------------------------------------
        case WM_MOUSEMOVE:
        case WM_LBUTTONDOWN: case WM_LBUTTONUP: case WM_LBUTTONDBLCLK:
        case WM_RBUTTONDOWN: case WM_RBUTTONUP: case WM_RBUTTONDBLCLK:
        case WM_MBUTTONDOWN: case WM_MBUTTONUP: case WM_MBUTTONDBLCLK:
        case WM_XBUTTONDOWN: case WM_XBUTTONUP:
        case WM_MOUSEWHEEL:  case WM_MOUSEHWHEEL:
            // ImGui has already seen these. Consume them only when a panel is
            // open, so dragging a slider does not also move the camera.
            return IsAnyWindowOpen();

        default:
            break;
    }
    return false;
}

// ---------------------------------------------------------------------------
//  Summon (M2)
//
//  M2 proves the command surface. The actual entity creation needs the ECS
//  world pointer, which is only obtainable by dynamic analysis (a live
//  breakpoint on the command dispatcher). Until that is done the honest
//  behaviour is: gate on the probe, report state, and do not fabricate a call.
//
//  What the summon key does as a fallback is write IsTame on the last wild
//  wolf we saw, through the game's own SetIsTame writer. That is the first
//  half of "召唤" and it exercises the whole tame path end to end.
//
//  The enemy->wildlife step is NOT done here: calling the engine's
//  wildlife_enemy_transformer (rva 0x480C70) from the render thread crashes
//  the game (verified 2026-10-18, fault at rva 0x9B8013). It has to be driven
//  by the game's own program dispatcher, which is still to be hooked.
// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
//  Summon
//
//  HISTORY — why this does not re-target a wolf any more.
//  The original design was "find the last wild beast the player met and tame
//  it". That cannot work in an open world: the game streams entities in and out
//  around the player, so leaving the area destroys the entity and its id, and
//  the remembered id then refers to nothing. A production session showed
//  exactly this — `last wild wolf : (none seen)` while the player was standing
//  in a forest.
//
//  The spawn factory (rva 0x97B790) takes a template GUID, not a position, and
//  does not require any wolf to be nearby, so summoning means "create one from
//  the wolf template". Position is applied afterwards via MoveEntity.
// ---------------------------------------------------------------------------
void RequestSummon() {
    using namespace wolfmount;

    if (!entityops::ResolveManager()) {
        g_lastAction = "entity manager not resolved yet - enter a world";
        return;
    }

    const entityops::NamedTemplate* t = entityops::LookupTemplate("wolf");
    if (!t) {
        g_lastAction = "wolf template missing from the built-in table";
        return;
    }
    uint8_t guid[16] = {0};
    if (!entityops::ParseGuid(t->guid, guid)) {
        g_lastAction = "wolf template GUID does not parse";
        return;
    }

    const int made = entityops::SpawnFollower(guid, 1, 3.0, 1);
    if (made <= 0) {
        // Say what actually failed instead of implying a wolf is on its way.
        g_lastAction = "spawn factory produced no live wolf (see the log)";
        return;
    }

    g_summonCount++;
    static char buf[128];
    // SpawnFollower already rewrote each wolf's Faction to PlayerAlly (a fresh
    // wolf would otherwise bite the player) and enrolled it in the follow set,
    // so this reports the state rather than promising a later step.
    snprintf(buf, sizeof(buf),
             "spawned %d wolf, faction -> PlayerAlly, following (%d in set)",
             made, entityops::FollowCount());
    g_lastAction = buf;
}

const char* RuntimeStatus() {
    const auto& probe = wolfmount::ecs::Probe();
    static char buf[128];
    snprintf(buf, sizeof(buf), "%s (%d/7 ECS features)",
             probe.status, probe.featuresFound);
    return buf;
}

bool IsMenuOpen() { return g_menuOpen; }

bool IsAnyWindowOpen() { return g_menuOpen || g_consoleOpen; }

// ---------------------------------------------------------------------------
//  Menu
// ---------------------------------------------------------------------------
void DrawMenu() {
    if (!g_menuOpen) return;

    ImGui::SetNextWindowSize(ImVec2(460, 0), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("WolfMount - 狼坐骑", &g_menuOpen)) {
        ImGui::End();
        return;
    }

    Settings& s = g_settings;

    ImGui::TextColored(ImVec4(0.75f, 0.55f, 0.25f, 1.0f),
                       "Enshrouded 1.0  Wolf Mount");
    ImGui::Separator();

    // ---- key bindings ------------------------------------------------------
    if (ImGui::CollapsingHeader("键位绑定", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Text("召唤坐骑键:");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1, 1, 0.4f, 1), "%s", KeyName(s.summonKey));
        ImGui::SameLine();
        if (ImGui::SmallButton("rebind##summon")) {
            // Simple cycle-based rebinding: click repeatedly to step through
            // common keys. A click-to-listen variant replaces this later.
            static const int cycle[] = { 'Y', 'G', 'H', 'J', 'K', 'L', 'T', 'R', 'B', 'V' };
            static int idx = 0;
            idx = (idx + 1) % (int)(sizeof(cycle) / sizeof(cycle[0]));
            s.summonKey = cycle[idx];
            SaveSettings();
        }
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("点击循环切换候选键位");

        ImGui::Text("菜单开关键:");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1, 1, 0.4f, 1), "%s", KeyName(s.menuKey));

        ImGui::Text("控制台开关键:");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1, 1, 0.4f, 1), "%s", KeyName(s.consoleKey));
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("命令控制台,与菜单互斥(打开一个会关闭另一个)");
    }

    // ---- features ---------------------------------------------------------
    if (ImGui::CollapsingHeader("功能", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::Checkbox("启用坐骑", &s.mountEnabled);
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("关闭后完全停用骑乘相关逻辑");

        ImGui::Checkbox("火把击杀驯化", &s.tameOnTorchKill);
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("用火把(火焰伤害)打中野狼时自动写入 IsTame 驯化");
        // Keep the hook rule in sync with the checkbox every frame.
        wolfmount::gamehooks::SetTorchTameEnabled(s.tameOnTorchKill);

        ImGui::Checkbox("狼并肩作战", &s.combatFollowEnabled);
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("将狼改为友军阵营,复用其战斗 AI");

        ImGui::SliderInt("最大驯服数量", &s.maxWolves, 1, 8);
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("游戏内最多存在多少头已驯服的狼");
    }

    // ---- runtime capability (M2) ------------------------------------------
    if (ImGui::CollapsingHeader("运行时能力", ImGuiTreeNodeFlags_DefaultOpen)) {
        const auto& probe = wolfmount::ecs::Probe();

        auto Row = [](const char* label, bool ok, const char* hint) {
            ImGui::TextColored(ok ? ImVec4(0.4f, 1.0f, 0.4f, 1.0f)
                                  : ImVec4(1.0f, 0.45f, 0.4f, 1.0f),
                               ok ? "[x]" : "[ ]");
            ImGui::SameLine();
            ImGui::Text("%s", label);
            if (ImGui::IsItemHovered() && hint) ImGui::SetTooltip("%s", hint);
        };

        Row("adminSpawnCommand - 生成实体", probe.hasAdminSpawnCommand,
            "keen::ecs::AdminSpawnCommand,含 followPlayer 字段");
        Row("adminDebugEnemyAction - 驯化命令", probe.hasAdminEnemyAction,
            "携带 EnemyDebugAction::SetTamed / ResetTamed");
        Row("IsTame 语义 - 驯化后停用野兽 AI", probe.hasIsTameSemantics,
            "文档: 'If set to false the Wildlife behavior won't run if the Wildlife is tamed'");
        Row("TameWildlifeEvent - 驯化事件", probe.hasTameWildlifeEvent,
            "keen::actor::TameWildlifeEvent");
        Row("HookShotAnchorSubEntity - 狼背挂点", probe.hasHookAnchor,
            "狼身上已有 Root - localOffset(0,1,0)");
        Row("addImpactHierarchy - 父子实体层级", probe.hasImpactHierarchy,
            "挂载玩家到狼的机制");
        Row("Enemy01BehaviorState - 战斗同伴 AI", probe.hasCompanionAI,
            "Base_Companion 同款,阵营 Player");

        ImGui::Separator();
        ImGui::Text("状态: %s", RuntimeStatus());
        ImGui::Text("召唤尝试: %d 次", g_summonCount);
        ImGui::TextDisabled("上次操作: %s", g_lastAction);

        // Game hook status: what is actually intercepted right now.
        ImGui::Separator();
        bool hooked = wolfmount::gamehooks::IsActive();
        ImGui::TextColored(hooked ? ImVec4(0.4f,1.0f,0.4f,1.0f)
                                  : ImVec4(1.0f,0.7f,0.3f,1.0f),
                            hooked ? "游戏钩子: 已就绪" : "游戏钩子: 未激活");
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("SendEvent 入口(rva 0x955400)读取 HitEvent;\n"
                              "Enqueue(rva 0x952400)写组件\n"
                              "GetCtx(rva 0x9B0860)获取世界上下文");

        bool haveCtx = wolfmount::gamehooks::HasWorldContext();
        ImGui::TextColored(haveCtx ? ImVec4(0.4f,1.0f,0.4f,1.0f)
                                   : ImVec4(1.0f,0.7f,0.3f,1.0f),
                           haveCtx ? "世界上下文: 已获取"
                                   : "世界上下文: 等待(需进世界)");
        ImGui::Text("GetCtx 调用: %d", wolfmount::gamehooks::CtxQueryCount());
        ImGui::Text("Enqueue 调用: %d", wolfmount::gamehooks::EnqueueCount());
        ImGui::Text("驯化写入: %d", wolfmount::gamehooks::TameIssuedCount());
        ImGui::Text("火把规则触发: %d", wolfmount::gamehooks::TorchTameCount());
        ImGui::Text("阵营改写: %d", wolfmount::gamehooks::FactionIssuedCount());
        if (wolfmount::gamehooks::HasEntityStore()) {
            ImGui::TextColored(ImVec4(0.4f,1.0f,0.4f,1.0f),
                               "实体表: 可访问");
        } else {
            ImGui::TextDisabled("实体表: 未获取");
        }

        // The summon path no longer depends on having met a wolf: an open world
        // streams entities in and out, so a remembered wild-beast id is gone as
        // soon as the player walks away. Summon spawns from the wolf template
        // instead, so this line is informational only.
        const uint32_t wolf = wolfmount::gamehooks::LastWildBeast();
        ImGui::Text("最近识别的野狼: ");
        ImGui::SameLine();
        if (wolf) {
            ImGui::TextColored(ImVec4(0.4f,1.0f,0.4f,1.0f), "entity %u", wolf);
        } else {
            ImGui::TextDisabled("附近没有(不影响召唤)");
        }

        // wildlife 改造 (M6): the engine's own enemy->wildlife program.
        // REFUSED, not failed: calling the transformer from the render thread
        // crashes the game (fault at rva 0x9B8013). It has to be driven by the
        // game's own program dispatcher, which is still to be hooked.
        ImGui::Text("wildlife 改造: ");
        ImGui::SameLine();
        ImGui::TextColored(ImVec4(1.0f,0.7f,0.3f,1.0f), "已禁用(直接调用会崩溃)");
    }

    // ---- taming state (M3) ------------------------------------------------
    if (ImGui::CollapsingHeader("驯化状态", ImGuiTreeNodeFlags_DefaultOpen)) {
        auto ts = wolfmount::tame::Snapshot();

        ImGui::TextDisabled("%s", wolfmount::tame::RulesText());

        const char* owned = (ts.tamedCount > 0) ? "是 (唯一一头)" : "否";
        ImGui::Text("已驯化: ");
        ImGui::SameLine();
        ImGui::TextColored(ts.tamedCount > 0 ? ImVec4(0.4f,1.0f,0.4f,1.0f)
                                             : ImVec4(0.7f,0.7f,0.7f,1.0f),
                           "%s", owned);

        ImGui::Text("火把驯化次数: %d", ts.convertedKills);
        ImGui::Text("被忽略的火把击杀: %d", ts.ignoredKills);
        ImGui::Text("非火把击杀: %d", ts.wolfKillsWithoutTorch);

        if (ts.tamedGuid) {
            ImGui::TextDisabled("驯服的模型: %s", ts.tamedGuid);
        }

        if (ImGui::SmallButton("重置驯化状态")) {
            wolfmount::tame::Reset();
        }
    }

    // ---- combat follow plan (M4) ------------------------------------------
    if (ImGui::CollapsingHeader("战斗跟随方案", ImGuiTreeNodeFlags_DefaultOpen)) {
        auto plan = wolfmount::follow::BuildPlan();

        ImGui::TextDisabled("%s", wolfmount::follow::Describe(plan));

        ImGui::Separator();
        ImGui::Text("狼自身已具备(无需新增 AI):");
        ImGui::BulletText("CombatTargetActor / ControlCombatTarget / SelectedTargets");
        ImGui::BulletText("Enemy01BehaviorState + EnemyArsenalReference");
        ImGui::BulletText("PathFinder / PathWalker / SteeringLocomotion");
        ImGui::BulletText("Aggro.applyEnemyValue = true(狼天生有仇恨)");

        ImGui::Separator();
        ImGui::Text("需要修改的字段:");
        ImGui::BulletText("Faction: %s -> %s", plan.faction.from, plan.faction.to);
        ImGui::BulletText("添加 IsTame(抑制敌对野兽行为)");
        ImGui::BulletText("添加 Animal / AnimalSaved / NetworkAnimal");

        ImGui::Separator();
        ImGui::TextColored(ImVec4(1.0f, 0.7f, 0.3f, 1.0f), "必须避免:");
        ImGui::BulletText("LifeTime(会让狼过期消失)");
        ImGui::BulletText("Boss / BossHealthBar");
        ImGui::BulletText("不可关闭 Aggro(否则退化为被动宠物)");

        ImGui::TextDisabled("方案校验: %s", plan.valid ? "通过" : "未通过");
    }

    // ---- mount state (M5) -------------------------------------------------
    if (ImGui::CollapsingHeader("骑乘状态", ImGuiTreeNodeFlags_DefaultOpen)) {
        auto ms = wolfmount::mount::Snapshot();
        auto slot = wolfmount::mount::GetAttachSlot();
        auto cam = wolfmount::mount::GetCameraPlan();

        ImGui::TextDisabled("%s", wolfmount::mount::StepText());

        const char* st = ms.mounted ? "骑乘中" : "未骑乘";
        ImGui::Text("状态: ");
        ImGui::SameLine();
        ImGui::TextColored(ms.mounted ? ImVec4(0.4f,1.0f,0.4f,1.0f)
                                      : ImVec4(0.7f,0.7f,0.7f,1.0f),
                           "%s", st);

        ImGui::Text("挂载: %s  偏移 (%.1f, %.1f, %.1f)",
                    slot.slot, slot.localX, slot.localY, slot.localZ);
        ImGui::Text("骑乘相机: %s", cam.mountCamera);
        ImGui::Text("坐姿: %s", cam.poseCamera);
        ImGui::Text("接管事件: %s / %s", cam.enterEvent, cam.exitEvent);
        ImGui::Text("上狼/下狼: %d / %d 次", ms.enters, ms.exits);
        ImGui::TextDisabled("上次转换: %s", ms.lastTransition);

        // Mount/dismount. The state machine in mount.cpp owns the transition
        // bookkeeping; the entity side lives in entityops (MountOnto copies
        // the wolf's transform onto the player each frame). A failed mount
        // must NOT be recorded as an enter, or the menu would claim the player
        // is riding when nothing is attached.
        if (ImGui::SmallButton(ms.mounted ? "下狼" : "上狼")) {
            if (ms.mounted) {
                if (wolfmount::mount::ExitMount()) entityops::Dismount();
            } else {
                const uint32_t wolf = entityops::FollowCount() > 0
                                          ? entityops::FollowAt(0)
                                          : entityops::LastFollower();
                if (wolf == 0) {
                    g_lastAction = "没有可骑的狼(先召唤一只)";
                } else if (entityops::MountOnto(wolf)) {
                    wolfmount::mount::SetHasWolf(true);
                    wolfmount::mount::TryEnterMount();
                } else {
                    g_lastAction = "上狼失败(详见日志)";
                }
            }
        }
        if (ImGui::IsItemHovered())
            ImGui::SetTooltip("把玩家坐标复制到狼背(+1.0 m);相机与坐姿未接管");
    }

    // ---- progress ---------------------------------------------------------
    if (ImGui::CollapsingHeader("进度", ImGuiTreeNodeFlags_DefaultOpen)) {
        ImGui::BulletText("M1 Vulkan Layer: 完成");
        ImGui::BulletText("M2 生成命令定位: 完成(7/7 ECS 签名)");
        ImGui::BulletText("M3 火把驯化规则: 完成(43 项测试)");
        ImGui::BulletText("M4 战斗跟随方案: 完成(17 项测试)");
        ImGui::BulletText("M5 骑乘框架: 完成(31 项测试)");
        ImGui::BulletText("M6 输入重定向: 待开启(需 ECS 分发器)");
    }

    if (s.showDebug) {
        ImGui::Separator();
        ImGui::Text("debug: %.1f FPS", ImGui::GetIO().Framerate);
        const auto& probe = wolfmount::ecs::Probe();
        ImGui::Text("module: %p", (void*)probe.module);
        ImGui::Text("adminSpawnCommandStr: %p [%s]",
                    (void*)probe.adminSpawnCommandStr, probe.adminSpawnCommandSection);
    }

    ImGui::Separator();
    ImGui::TextDisabled("按 %s 开关此菜单", KeyName(s.menuKey));
    if (g_consoleOpen) {
        ImGui::TextDisabled("控制台已打开 (按 %s 关闭)", KeyName(s.consoleKey));
    }

    ImGui::End();
}

// ---------------------------------------------------------------------------
//  Console window (independent of the menu)
//
//  The console MUST be drawn from here, not from the end of DrawMenu: DrawMenu
//  returns immediately when the F8 menu is closed, so anything at its tail
//  would be invisible until the menu happened to be open. The F9 console is
//  meant to work while playing, with no menu in the way.
// ---------------------------------------------------------------------------
void DrawConsole() {
    wolfmount::console::ui::Draw(&g_consoleOpen);
}

// ---------------------------------------------------------------------------
//  M1 stub removed - summon is implemented above.
// ---------------------------------------------------------------------------
} // namespace wolfmount::mod
