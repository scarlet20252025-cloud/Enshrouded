#pragma once
// ============================================================================
//  WolfMount — command console UI
//
//  Split from console.h so the command layer stays renderer-free and testable.
// ============================================================================

namespace wolfmount::console::ui {

// Draw the console panel; `open` is the visibility flag.
void Draw(bool* open);

// True while the text field has keyboard focus, so the layer stops treating
// keystrokes as game input.
bool WantsKeyboard();

} // namespace wolfmount::console::ui
