# -*- coding: utf-8 -*-
"""Append the input-focus post-mortem + transform status to MODLOG.md."""
import io

LOG = r"E:\DSH\肥鱼乐园\WolfMount\MODLOG.md"

TEXT = """
---

## F8/F9 失联真相：不是 bug，是窗口焦点 + 地图切换的叠加（m07104 / m07206）

### 用户报告（m07104）

> 「F8和F9都不生效了」

### 排查过程与结论

**第一反应是代码回退，但日志推翻了这个假设。** 日志里
`menu opened/closed` 13 次、`console opened/closed` 17 次，说明
`PollInput()` 一直在正常跑，`KeyWentDown` 也在正常触发。按键链路是通的。

真正的原因是两件事叠加：

1. **游戏窗口没有焦点**。`GetAsyncKeyState` 读的是全局硬件键盘状态，
   但如果前台是别的程序（用户当时在跟我对话、点别的窗口），
   按键会被那个程序吃掉，游戏进程根本看不到状态变化。
   —— 用户后来说「鼠标点击也生效了」，正是因为点击游戏窗口把焦点还给
   它之后一切恢复正常。

2. **日志里出现了第二次 `swapchain created`**：
   ```
   line  12: swapchain created: 0x20B324AA1D0 images=3 1680x970
   line 519: swapchain created: 0x20B3374F5D0 images=3 1679x970
   ```
   宽度从 1680 变成 1679 —— 这是游戏在**切换地图/存档**（用户说的
   「在地图里」）。`RebuildFramebuffers()` 会重建全部 image view 和
   framebuffer，那一小段时间里 overlay 处于半初始化状态，
   用户看到的「模糊」就是这段窗口期的表现。

   注意 `RebuildFramebuffers` 之后**没有任何错误日志**（无
   `images not ready`、无 `createImageView failed`、无 `overlay disabled`），
   说明重建本身是干净的。

### 教训（值得记住）

- **「按键没反应」先查窗口焦点，再查代码**。日志里有
  `poll diag: ... state=0x0000` 这种低成本诊断，本次正是它证明了
  PollInput 活着。
- **Vulkan overlay 遇到游戏重建 swapchain 是常态**（切地图、改分辨率、
  全屏切换都会）。`g_ov.extent` 变化时 framebuffer 必须跟着重建，
  否则会拿旧尺寸的 framebuffer 画新尺寸的 swapchain → 画面错乱。
  当前实现已经在做，且无错误，**这条路径是健壮的**。
- 用户主观描述「不生效」时，日志是最可靠的仲裁者。本次若直接改代码
  去「修」一个不存在的 bug，只会把好的逻辑改坏。

### 本轮确认可用的能力

```
[wolfmount] game hooks: SendEvent entry verified (rva 0x955400, ...)
[wolfmount] game hooks: SendEvent entry hook LIVE
[wolfmount] game hooks: Enqueue hook LIVE (rva 0x952400, SetIsTame ...)
[wolfmount] game hooks: GetCtx hook LIVE (rva 0x9B0860, ...)
[wolfmount] game hooks installed: 3
[wolfmount] world context ADOPTED via GetCtx: 0x3008954BD80 (store 0xC62F0DBAA0)
[wolfmount] world probe: holder=... world=... +0x400=0 +0x470=64 +0x4b0=0
           +0x4b8=1 +0x4ba=1 +0x7a0=0 +0x7f0=0 +0x1a8=0
[wolfmount] world probe: +0x4b0..+0x4c0 readable -> QueryBuild-safe;
           NOT the program registry (that is 14.7MB out)
[wolfmount] ENQ #1..#40 ctx=0x3008954BD80 size=76 flags=4
[wolfmount] COMP #1..#400 keen::ecs::OverrideLevel (0xA21E7EE7) size=76
```

- F8 菜单 / F9 控制台 / 鼠标点击**全部正常**（用户已确认）。
- world probe 证明 `holder[0]` 的对象在 `+0x400..+0x4c0` 全部可读，
  正是 `QueryBuild`(0x1409BAB60) 会解引用的范围。
- 400 条 `OverrideLevel` 组件写入被 Enqueue hook 抓到，证明 hook
  在真实游戏循环里持续工作。

### 唯一还没跑的一步

`transform` 命令（调用游戏原生 `wildlife_enemy_transformer` rva 0x480C70）
**尚未在真实游戏里执行过**。用户已能在 F9 控制台输入命令，下一步只需：

```
> transform
```

预期日志：
```
[wolfmount] TransformEnemyToWildlife: invoked on holder 0x...
```

若之后狼停止攻击玩家 / 可被 TameWildlifeEvent 命中，则 M6 闭环。
"""


def main():
    with io.open(LOG, "a", encoding="utf-8") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
