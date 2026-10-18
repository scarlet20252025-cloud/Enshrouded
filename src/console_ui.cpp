// ============================================================================
//  WolfMount — command console UI (ImGui)
//
//  Drawing only. All command logic lives in console.cpp, which has no renderer
//  dependency so it can be unit-tested head-less.
// ============================================================================

#include <imgui.h>

#include "console_ui.h"
#include "console.h"

namespace wolfmount::console::ui {
namespace {

char g_input[512] = {0};
bool g_scrollToBottom = false;
bool g_focusInput = false;
bool g_wasOpen = false;

} // namespace

bool WantsKeyboard() { return g_focusInput; }

void Draw(bool* open) {
    if (!open || !*open) {
        // Reset focus when the window closes, otherwise the game would stay
        // keyboard-locked forever.
        g_focusInput = false;
        g_wasOpen = false;
        return;
    }

    ImGui::SetNextWindowSize(ImVec2(620, 360), ImGuiCond_FirstUseEver);
    if (!ImGui::Begin("WolfMount — 控制台", open)) {
        g_focusInput = false;
        ImGui::End();
        return;
    }

    const float footer = ImGui::GetStyle().ItemSpacing.y
                       + ImGui::GetFrameHeightWithSpacing();

    ImGui::BeginChild("##scroll", ImVec2(0, -footer), ImGuiChildFlags_Borders);
    for (const auto& s : Scrollback()) ImGui::TextUnformatted(s.c_str());
    if (g_scrollToBottom) {
        ImGui::SetScrollHereY(1.0f);
        g_scrollToBottom = false;
    }
    ImGui::EndChild();

    if (!g_wasOpen) {
        g_focusInput = true;
        g_wasOpen = true;
    }

    if (g_focusInput) ImGui::SetKeyboardFocusHere();
    ImGui::SetNextItemWidth(-1);

    const bool submitted = ImGui::InputText(
        "##cmd", g_input, sizeof(g_input),
        ImGuiInputTextFlags_EnterReturnsTrue);

    g_focusInput = ImGui::IsItemActive();

    if (submitted) {
        const std::string line(g_input);
        g_input[0] = '\0';
        if (!line.empty()) {
            Scrollback().push_back("> " + line);
            Execute(line);
            g_scrollToBottom = true;
        }
        g_focusInput = true;
    }

    ImGui::End();
}

} // namespace wolfmount::console::ui
