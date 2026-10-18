# -*- coding: utf-8 -*-
"""Append the transform-crash post-mortem to MODLOG.md."""
import io

LOG = r"E:\DSH\肥鱼乐园\WolfMount\MODLOG.md"

TEXT = """
---

## transform 崩溃 post-mortem：游戏原生 transformer 不能从外部调（m07215）

### 崩溃现场

用户在 F9 控制台输入 `transform`，立即崩溃：

```
[wolfmount] *** EXCEPTION 0xC0000005
[wolfmount]     faulting addr : enshrouded.exe+0x9B8013
[wolfmount]     raw address   : 00007FF6876E8013
[wolfmount]     instr bytes   : 48 8B 48 58 48 8B C2 48 89 0A C3 CC CC 48 8B 01
[wolfmount]     access        : read at 000000000044026A
[wolfmount]     rip=00007FF6876E8013 rsp=000000C629EFB7B8 rbp=000000C629EFB8C0
[wolfmount]     rcx=00000300840EFA22 rdx=000000C629EFB8F0 r8=000000C62F0DB970 r9=000000C62F0DBAA0
```

### 定位

崩在 `enshrouded.exe+0x9B8013`，即 `QueryNext`(0x1409B8010) 的第 4 字节：

```
1409b8010: 48 8b 01        movq (%rcx),%rax        ; rax = [rcx]
1409b8013: 48 8b 48 58     movq 0x58(%rax),%rcx    ; rcx = rax->0x58   <-- 崩在这
1409b8017: 48 8b c2        movq %rdx,%rax
1409b801a: 48 89 0a        movq %rcx,(%rdx)
1409b801d: c3              ret
```

反推 rax：`0x000000000044026A - 0x58 = 0x440212`。
即 `[rcx]` 返回了 `0x440212` 这个垃圾值，而崩溃时的
`rcx = 0x00000300840EFA22` —— **不是我们的 holder**（holder 是
`0x000000C62F0DBAA0`，出现在 `r9` 里）。

`rbp - rsp = 0x108`，与 transformer 的 `sub rsp,0x108` 吻合，
说明确实是在 `wildlife_enemy_transformer` 的栈帧里。

### 结论：holder 传对了，但查询对象不是

关键事实：**transformer 成功走过了 `QueryBuild`(0x9BAB60) 和
`QueryRun`(0x9B5A50)** —— 我们传的 holder 是对的，`holder[0]` 就是
QueryBuild 需要的 world。前面所有关于 holder 形状的分析全部成立。

崩在后一步：transformer 在自己栈上建的 0xa8 字节查询对象里含有关联指针，
那些指针**只有在游戏自己的 program dispatcher 驱动这个 handler 时才有效**。
从外部（渲染线程、任意帧位置）调用，其中一个指针是垃圾，
`world->[0x58]` 就解引用了非法地址。

### 修复

`TransformEnemyToWildlife()` 不再调用游戏函数，直接返回 false 并记日志：

```cpp
(void)fn;
g_lastTransformCount.store(0, std::memory_order_relaxed);
WM_MOD_LOG("[wolfmount] TransformEnemyToWildlife: REFUSED - the engine's "
           "wildlife_enemy_transformer can only be driven by the game's "
           "own dispatcher (see MODLOG crash post-mortem)");
return false;
```

`CmdTransform` 保留注册（不静默消失），但返回 `NotAvailable` 并说明原因。
`RequestSummon()` 去掉 transform 步骤，只保留 `TameEntity`。
菜单里的「wildlife 改造」状态改为「已禁用(直接调用会崩溃)」。

### 下一步（未完成）

要 hook 游戏自己的 program dispatcher：遍历 `world+0x746350`、
stride `0x1f20`、调 `slot+0x28` 的那段代码。找到了就能让游戏自己跑
transformer，或者在其调用我们的目标 handler 时注入逻辑。

已知遍历 program 表的代码在 `0x140A17A33`（`leaq 0x746350(%r14),%r9` +
`imul $0x1f20`），但那段是在置位标志
（`slot+0x2c0` / `slot+0x570` 的 bitset），**不是**调 handler 的地方。
`callq *0x28(reg)` 在全映像有 123 处，尚未筛出 dispatcher。

### 教训

- **「游戏有这个函数」不等于「我能调它」**。ECS 程序 handler 依赖
  dispatcher 建立好的查询上下文，是典型的有状态调用点。
- 崩溃指令字节能直接反推出越界基址（`faultaddr - disp = reg`），
  比看调用栈快；本次靠这个在 1 分钟内定位到 `rax = 0x440212`。
- VEH 打印的模块名可能不准（本次 `faulting addr` 直接给出了
  `enshrouded.exe+0x9B8013`，是准确的）。
- 控制台命令必须在发现崩溃后**立即**改成显式拒绝，不能留着一个会崩的入口。
"""


def main():
    with io.open(LOG, "a", encoding="utf-8") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
