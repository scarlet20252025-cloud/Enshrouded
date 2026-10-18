#!/usr/bin/env python3
r"""Repair mojibake in src/mod.cpp using ASCII-only unicode escapes.

All replacement text is written as \uXXXX escapes so this file is pure ASCII
and immune to any console/pipe encoding round-trip.
"""
import io
import sys

PATH = r"E:\DSH\肥鱼乐园\WolfMount\src\mod.cpp"


def u(s):
    """Convert \\uXXXX escapes in an ASCII literal to real characters."""
    return s.encode("ascii").decode("unicode_escape")


# line number (1-based) -> corrected full text
FIX = {
    431: u('                           haveCtx ? "\u4e16\u754c\u4e0a\u4e0b\u6587: \u5df2\u83b7\u53d6"'),
    432: u('                                   : "\u4e16\u754c\u4e0a\u4e0b\u6587: \u7b49\u5f85(\u9700\u8fdb\u4e16\u754c)");'),
    440: u('                               "\u5b9e\u4f53\u8868: \u53ef\u8bbf\u95ee");'),
    442: u('            ImGui::TextDisabled("\u5b9e\u4f53\u8868: \u672a\u83b7\u53d6");'),
    456: u('    if (ImGui::CollapsingHeader("\u9a6f\u5316\u72b6\u6001", ImGuiTreeNodeFlags_DefaultOpen)) {'),
    461: u('        const char* owned = (ts.tamedCount > 0) ? "\u662f (\u552f\u4e00\u4e00\u5934)" : "\u5426";'),
    462: u('        ImGui::Text("\u5df2\u9a6f\u5316: ");'),
    470: u('        ImGui::Text("\u975e\u706b\u628a\u51fb\u6740: %d", ts.wolfKillsWithoutTorch);'),
    473: u('            ImGui::TextDisabled("\u9a6f\u670d\u7684\u6a21\u578b: %s", ts.tamedGuid);'),
    476: u('        if (ImGui::SmallButton("\u91cd\u7f6e\u9a6f\u5316\u72b6\u6001")) {'),
    502: u('        ImGui::BulletText("LifeTime(\u4f1a\u8ba9\u72fc\u8fc7\u671f\u6d88\u5931)");'),
    510: u('    if (ImGui::CollapsingHeader("\u9a91\u4e58\u72b6\u6001", ImGuiTreeNodeFlags_DefaultOpen)) {'),
    517: u('        const char* st = ms.mounted ? "\u9a91\u4e58\u4e2d" : "\u672a\u9a91\u4e58";'),
    518: u('        ImGui::Text("\u72b6\u6001: ");'),
    524: u('        ImGui::Text("\u6302\u8f7d: %s  \u504f\u79fb (%.1f, %.1f, %.1f)",'),
    529: u('        ImGui::Text("\u4e0a\u72fc/\u4e0b\u72fc: %d / %d \u6b21", ms.enters, ms.exits);'),
    538: u('            ImGui::SetTooltip("\u672c\u5730\u72b6\u6001\u673a\u6f14\u793a;\u5b9e\u9645\u6302\u8f7d\u9700 M6 \u5206\u53d1\u5668");'),
    545: u('        ImGui::BulletText("M3 \u706b\u628a\u9a6f\u5316\u89c4\u5219: \u5b8c\u6210(43 \u9879\u6d4b\u8bd5)");'),
    546: u('        ImGui::BulletText("M4 \u6218\u6597\u8ddf\u968f\u65b9\u6848: \u5b8c\u6210(17 \u9879\u6d4b\u8bd5)");'),
    547: u('        ImGui::BulletText("M5 \u9a91\u4e58\u6846\u67b6: \u5b8c\u6210(31 \u9879\u6d4b\u8bd5)");'),
    548: u('        ImGui::BulletText("M6 \u8f93\u5165\u91cd\u5b9a\u5411: \u5f85\u5f00\u542f(\u9700 ECS \u5206\u53d1\u5668)");'),
    561: u('    ImGui::TextDisabled("\u6309 %s \u5f00\u5173\u6b64\u83dc\u5355", KeyName(s.menuKey));'),
    570: u('//  M1 stub removed - summon is implemented above.'),
}

PROBES = [
    "\u72fc\u5750\u9a91",        # 狼坐骑
    "\u952e\u4f4d\u7ed1\u5b9a",  # 键位绑定
    "\u9a6f\u5316\u72b6\u6001",  # 驯化状态
    "\u9a91\u4e58\u72b6\u6001",  # 骑乘状态
    "\u5f00\u5173\u6b64\u83dc\u5355",  # 开关此菜单
]


def main():
    with io.open(PATH, encoding="utf-8") as f:
        lines = f.read().split("\n")
    changed = 0
    for num, text in sorted(FIX.items()):
        idx = num - 1
        if idx >= len(lines):
            print("line %d out of range" % num)
            continue
        if "\ufffd" not in lines[idx] and "?" not in lines[idx]:
            print("line %d already clean" % num)
            continue
        lines[idx] = text
        changed += 1
    with io.open(PATH, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(lines))
    sys.stdout.write("rewrote %d lines\n" % changed)

    with io.open(PATH, encoding="utf-8") as f:
        body = f.read()
    bad = body.count("\ufffd")
    sys.stdout.write("remaining U+FFFD: %d\n" % bad)
    for p in PROBES:
        sys.stdout.write("contains %s: %s\n" % (p, p in body))
    # every literal char printed as escapes so the console encoding cannot mangle it
    for num in (431, 456, 461, 517, 561):
        sys.stdout.write("L%d = %r\n" % (num, lines[num - 1].encode("unicode_escape").decode("ascii")))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
