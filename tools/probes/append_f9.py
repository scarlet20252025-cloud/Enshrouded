# -*- coding: utf-8 -*-
"""Append the F9-console fix + world-holder findings to MODLOG.md."""
import io

LOG = r"E:\DSH\肥鱼乐园\WolfMount\MODLOG.md"

TEXT = """
---

## F9 控制台修好 + world holder 形状确认（用户截图反馈后）

### 用户反馈（m06919，逐字）

> 「F9按不出终端，F8才能按出来，而且跟原来的F8菜单重合了，遮挡了原来菜单的功能」

截图显示：WolfMount 菜单窗口标题是「WolfMount — 控制台」，里面既有 `> status`
回显也有菜单内容 —— 说明控制台当时是**画在菜单里面**的。

### 根因

`src/mod.cpp` 的 `DrawMenu()` 第一行是：

```cpp
void DrawMenu() {
    if (!g_menuOpen) return;      // <-- F8 菜单没开就直接返回
    ...
    ImGui::End();
    wolfmount::console::ui::Draw(&g_consoleOpen);   // 在 return 之后，永远画不到
}
```

控制台画在 `DrawMenu()` 尾部，而 F8 菜单关闭时该函数第一行就 return，
所以 F9 控制台在正常游戏状态下**完全不可见**。只有先按 F8 开出菜单，
才顺带看到控制台 —— 这就是用户说的「F8 才能按出来」。

### 修复

1. `src/mod.cpp`：控制台移出 `DrawMenu()`，新增独立入口
   ```cpp
   void DrawConsole() { wolfmount::console::ui::Draw(&g_consoleOpen); }
   ```
2. `src/layer.cpp` 帧循环（rva 附近，第 671 行之后）改为：
   ```cpp
   wolfmount::mod::DrawMenu();
   // The console is drawn OUTSIDE DrawMenu on purpose: DrawMenu returns early
   // when the F8 menu is closed, which would leave the F9 console undrawn
   // during normal play.
   wolfmount::mod::DrawConsole();
   ```
3. `src/mod.h`：新增 `void DrawConsole();` 与 `bool IsAnyWindowOpen();`
4. `src/mod.cpp` `OnWndProc` 的鼠标/键盘吞噬条件从 `g_menuOpen` 改为
   `IsAnyWindowOpen()`，否则控制台开着时点不到它自己的输入框。
5. `src/layer.cpp` 的 `MouseDrawCursor` 也从 `IsMenuOpen()` 改为
   `IsAnyWindowOpen()`，否则控制台开着时没有软件光标。

### 遮挡问题的修复：两个窗口互斥

用户在截图里遇到的第二个问题是控制台盖住菜单按钮。修法不是调位置
（ImGui 窗口可拖动，位置会变），而是**互斥**：

```cpp
if (KeyWentDown(g_settings.menuKey, menuWasDown)) {
    g_menuOpen = !g_menuOpen;
    ...
    // Opening the menu must never be blocked by a console sitting on top of
    // it, so the console steps aside whenever the menu takes over.
    if (g_menuOpen && g_consoleOpen) { g_consoleOpen = false; ... }
}
// 反向同理
if (... KeyWentDown(g_settings.consoleKey, consoleWasDown)) {
    g_consoleOpen = !g_consoleOpen;
    ...
    if (g_consoleOpen && g_menuOpen) { g_menuOpen = false; ... }
}
```

菜单「键位绑定」区现在也显示控制台键位，tooltip 说明互斥。

### 验证（日志实证）

```
[wolfmount] console opened (polled)
[wolfmount] menu opened (polled)
[wolfmount] console closed (menu took over)      <-- 互斥生效
[wolfmount] menu closed (polled)
[wolfmount] console opened (polled)              <-- F9 独立可用，无需 F8
[wolfmount] console closed (polled)
```

### 本轮同时修掉的另一个 bug：transform 的 holder 传错

`TransformEnemyToWildlife()` 原本传的是 `void* holder[2] = {world, nullptr}`
—— 一个栈上临时数组。虽然形状对，但**更重要的是搞错了 world 的来源**。

三个 transformer handler 的第一件事都是把 rcx 交给 `QueryBuild`
(0x1409BAB60)，而 `QueryBuild` 的开头是：

```
1409bab74: 4c 8b 09        movq (%rcx), %r9      ; r9 = *(void**)rcx
1409bab7d: 41 0f b6 81 b0 04 00 00  movzbl 0x4b0(%r9),%eax
```

即 `rcx` 必须是「`rcx[0]` 是 ECS world」的对象。而 `GetCtx` 是
`mov rax,[rcx]; mov rax,[rax+8]; ret`，即 `world = store[0][1]`。

**所以 `store` 本身就满足 QueryBuild 的要求**：`store[0]` 正是 GetCtx
解引用出来的那个对象，`store[0]+8` 就是 world。与其假设 GetCtx 的返回值
就是 world，不如直接把 GetCtx 的入参 `store` 当 holder 传下去。

```cpp
// src/gamehooks.cpp
std::atomic<void*> g_worldHolder{nullptr};   // 新增

void* DetourGetCtx(void* store) {
    void* ctx = g_getCtxTrampoline ? g_getCtxTrampoline(store) : nullptr;
    ...
    if (ctx && !g_worldCtx.load(...)) {
        if (LooksLikeQueue(ctx)) {
            g_worldCtx.store(ctx, ...);
            if (store) g_worldHolder.store(store, ...);   // <-- 新增
            WM_MOD_LOG("... world context ADOPTED via GetCtx: %p (store %p)", ctx, store);
            ProbeWorldCandidate(store);                   // <-- 新增，一次性自证
        } else { NoteContext(ctx); }
    }
    return ctx;
}

void* WorldHolder() { return g_worldHolder.load(...); }   // 新增导出

bool TransformEnemyToWildlife() {
    void* holder = WorldHolder();
    if (!holder) return false;
    fn(holder);        // 不再自造 holder 数组
    ...
}
```

`ProbeWorldCandidate(holder)` 会读 `holder[0]` 然后 dump
`+0x400 / +0x470 / +0x4b0 / +0x4b8 / +0x4ba / +0x7a0 / +0x7f0 / +0x1a8`
—— 正是 QueryBuild 会解引用的那组字段。它一次性打印，用来在真调
`wildlife_enemy_transformer` 之前先确认形状对不对。

### 仍未实测

`world probe` 那行日志**还没出现**，因为用户这次仍在主菜单
（无 `world context ADOPTED`、无 `ENQ #`）。下次进世界后应立即看到：

```
[wolfmount] world context ADOPTED via GetCtx: 00000300xxxxxxxx (store 000000xxxxxxxxxx)
[wolfmount] world probe: holder=000000xxxxxxxxxx world=00000300xxxxxxxx
           +0x400=.. +0x470=.. +0x4b0=.. +0x4b8=.. +0x4ba=.. +0x7a0=.. +0x7f0=.. +0x1a8=..
```

判定标准：`world` 非空、`+0x4b0/+0x4b8/+0x4ba` 是小整数（组件计数），
`+0x1a8` 是可疑指针。若 `holder[0]` 不可读，说明 store 不是 holder，
需要改回自造数组或另找 holder。

### 教训

- **ImGui 子窗口不能挂在会 early-return 的绘制函数尾部**。`DrawMenu()` 的
  `if (!g_menuOpen) return;` 让挂在它末尾的控制台永远画不出来。多个独立
  窗口必须各自从帧循环调用。
- 「两个窗口重叠」不要靠调位置解决（窗口会被拖动），要靠互斥状态机。
- 拿到一个指针后，先写一个只读 probe 把它会解引用的字段打出来，
  再拿它去调游戏的代码。比直接调用崩了再猜便宜得多。
"""


def main():
    with io.open(LOG, "a", encoding="utf-8") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
