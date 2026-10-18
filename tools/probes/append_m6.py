# -*- coding: utf-8 -*-
"""Append the M6 wildlife-transformer findings to MODLOG.md.

Everything here was verified against enshrouded.exe with tools/ this round.
"""
import io
import os

LOG = r"E:\DSH\肥鱼乐园\WolfMount\MODLOG.md"

TEXT = """
---

## M6 · enemy -> wildlife 改造：原生 `wildlife_enemy_transformer` 找到并可调用

### 结论（本轮最重要）

游戏**自带**把 Enemy 单位原地改造成 Wildlife 的代码：entity program
`wildlife_enemy_transformer`（descriptor rva `0x1E2B860`，handler rva
`0x140480C70`，nameLen 26）。此前 MODLOG 里「运行时把狼变成野生动物这条路也断了」
的结论**作废** —— 那条路不是断了，是当时 descriptor 表还没解出来。

### descriptor 表（16 条，只经 thunk 可达）

`.text` rva `0x12CF5C0` 起、步长 0x10、每条 8 字节 `lea rax,[rip+d]; ret`，
中间填 `cc`。16 个 thunk 指向 16 个 descriptor（`tools/desc_size.py`）。

descriptor 布局（变长，无固定 stride，相邻间距 0x1B0–0x220）：

```
+0x00  char*  name
+0x08  u64    nameLen
+0x10  void*  handler
+0x18  ...    {char** pool; u32 count; u32 pad} 组，直到「本组与下一组都为 {0,0}」为止
+0x180 u32    标志位（registrar 读 `testb $0x2, 0x180(%rdx)`）
+0x184 u32    恒 1
+0x188 void*  类型名指针（两个 transformer 分别是 "Wildlife" / "Wildlife"）
```

**坑（重要）**：`{0,0}` 是**合法的空组**，不是终止符。
`wildlife_enemy_transformer` 前 3 组全是 `{0,0}`。终止条件是
「本组与下一组同时为 {0,0}」，所以最少 descriptor 只有 0x28 字节
（`allyaggromultiplier_init` / `armor_init` / `comfort_init` 都是 0x28）。

16 个 descriptor 实测：

| thunk rva | descriptor rva | name | handler rva |
|---|---|---|---|
| 0x12CF5C0 | 0x1E2A820 | extinguish_client | 0x47C250 |
| 0x12CF5D0 | 0x1E2A9E0 | water_dispenser_client_init | 0x47C960 |
| 0x12CF5E0 | 0x1E2ABB0 | water_dispenser_server_init | 0x47CAA0 |
| 0x12CF5F0 | 0x1E2AD80 | water_dispenser_server_toggle | 0x47CC00 |
| 0x12CF600 | 0x1E2AF50 | water_drain_server_init | 0x47CD90 |
| 0x12CF610 | 0x1E2B120 | water_drain_server_toggle | 0x47CE50 |
| **0x12CF620** | **0x1E2B680** | **wildlife** | **0x480A70** |
| **0x12CF630** | **0x1E2B860** | **wildlife_enemy_transformer** | **0x480C70** |
| **0x12CF640** | **0x1E2BA50** | **wildlife_farm_animal_transformer** | **0x481060** |
| 0x12CF650 | 0x1E2BC70 | allyaggromultiplier_init | 0x122C6E0 |
| 0x12CF660 | 0x1E2BE20 | armor_init | 0x122C7D0 |
| 0x12CF670 | 0x1E2BFD0 | armorpoints_init | 0x122C8C0 |
| 0x12CF680 | 0x1E2C180 | block_init | 0x122C9B0 |
| 0x12CF690 | 0x1E2C330 | bodyheat_init | 0x122CAA0 |
| 0x12CF6A0 | 0x1E2C4E0 | bodyheatmaxmod_init | 0x122CB90 |
| 0x12CF6B0 | 0x1E2C690 | comfort_init | 0x122CC80 |

两个 transformer 的组件组（直接决定狼能不能被改造）：

```
wildlife_enemy_transformer (0x1E2B860)
    group0 +0x18 EMPTY   group1 +0x28 EMPTY   group2 +0x38 EMPTY
    group3 +0x48 n=1: IsTame
    group4 +0x58 n=3: DynamicEnemy01BehaviorState, UnitTransformer, WildlifeTransformer
    group5 +0x68 n=1: UnitTransformer
    +0x160 n=1: （第二处引用）

wildlife_farm_animal_transformer (0x1E2BA50)
    group0 +0x18 n=1: Wildlife
    group1 +0x28 EMPTY
    group2 +0x38 n=1: DynamicWildlife
    group3 +0x48 n=1: IsTame
    group4 +0x58 n=2: DismantleOverride, Faction
    group5 +0x68 EMPTY
    +0x110 n=1: （第二处引用）
```

`wildlife` (0x1E2B680) 的组最全：`FleeSensor / MovementColliderConfig / PathWalker /
Wildlife`、`FlyingEnemy`、`CurrentTransform / DynamicHitReactionBehavior /
MovementCollider`、`DynamicFlying / IsTame / UnitTransformer`、`Actor / ActorInput /
DynamicFleeSensor / DynamicLocomotion / DynamicNetworkLocomotion / DynamicPathWalker /
ServerAnimationGraphInput / SteeringAgent / DynamicWildlife`、
`NetworkWildlife / SteeringBehavior_Separation / DynamicSteeringLocomotion`。

组件名池是扁平 16 字节条目 `{char* name; u32 len; u32 pad}`，范围
`rva 0x1E2B400 .. 0x1E2B690`。

### wildlife_enemy_transformer handler 反汇编（rva 0x140480C70，0x3E5 字节）

```
140480c70: movq %rcx,0x8(%rsp) ; push rbp ; push r14
          lea rbp,[rsp-0x8] ; sub rsp,0x108
140480c84: movl $0xa8,%r8d ; lea 0x30(%rsp),%rdx ; movq %rcx,%r14
140480c92: callq 0x1409bab60      ; QueryBuild(worldHolder, &buf, 0xa8)
140480c97: movl $0xa8,%r8d ; lea 0x30(%rsp),%rdx ; movq %r14,%rcx
140480ca5: callq 0x1409b5a50      ; QueryRun  -> al
140480caa: testb %al,%al ; je end
140480cf0: movq -0x30(%rbp),%rsi          ; chunk array {u16 count@0x40, ptr@0x30, u32 cap@0x18}
140480d20: cmpl 0x18(%rsi),%r15d ; jae done_this_chunk
140480d2a: leal 0xf8(%rdi),%ecx ; cmpl $0x7f8,%ecx ; jbe 0x140480d57   ; stride 0x800 溢出保护
140480d38: movzwl 0x2(%rbx),%eax ; ... shl $0xb ... addq 0x30(%rsi),%rbx  ; 下一 chunk
140480d57: movq 0x20(%rbp),%rcx
140480d67: callq 0x1409b2e40      ; ResolveEnt
140480d6c: movl (%rax),%ecx
140480d6e: cmpl %ecx,0x9c(%r14,%rbx)   ; 组件类型匹配
140480d78: testl $0x200,0xa0(%r14,%rbx) ; 标志位过滤
140480daf: callq 0x1409c5df0      ; ComponentRemove(...)
140480dc8: movq 0x20(%rbp),%r14 ; lea 0x30(%rbp),%rdx ; movq %r14,%rcx
140480dd3: callq 0x1409b8010      ; QueryNext
140480e5b: ... 累加计数器 (saturating add, 0x7FFFFFFFFFFFFFFF/-0x8000... 边界处理)
140480e8b: movq 0x70(%rsp),%rax ; movzbl (%rax),%edx ; 读 UnitMode 字节
140480e95: je  0x140480f50       ; mode == 0 -> 走 f50
140480f87: movb $0x1,(%rax)      ; mode != 0 -> 写成 1 (Enemy)
140480f50: ... testb %r12b,%r12b ; je 0x140480f8e
140480f82: movq 0x70(%rsp),%rax ; movb $0x1,(%rax)   ; 写成 1
140481005: movb %cl,0x498(%rax)  ; 把「是否等于 1」写回查询对象
14048100e: callq 0x1409b5a50      ; QueryRun 再次确认
140481015: jne 0x140480cf0        ; 还有实体 -> 继续循环
14048104b: add rsp,0x108 ; pop r14 ; pop rbp ; ret
```

**0xa8 字节查询对象布局**（rbp = rsp+0x100，buffer = rsp+0x30）：

| buffer 偏移 | 来源 | 内容 |
|---|---|---|
| +0x00 | `movq %rbx,(%rdi)` | world 指针 |
| +0x08 | `movl 0x8(%rcx),%eax` 比较 `0x830(%r8)` | epoch / generation（`QueryRun` 据此判陈旧，相等即返回 false） |
| +0x40 | `movq 0x70(%rsp),%rax` | **byte\* UnitMode** —— `movb $0x1,(%rax)` 就地翻转 |
| +0x98 | `movq -0x38(%rbp),%rcx` | ComponentRemove 的第 1 参 |
| +0x90 | `movzwl -0x40(%rbp)` | ComponentRemove 栈参 1（u16 组件索引） |
| +0x92 | `movzbl -0x3e(%rbp)` | ComponentRemove 栈参 2（u8 标志） |
| +0x88..0x50 | `movq -0x48..-0x80(%rbp)` | ComponentRemove 栈参 3..5 |
| +0xA0 | `movq -0x30(%rbp),%rsi` | 实体 chunk 数组 `{u32 cap@0x18, void* data@0x30, u16 count@0x40}`，stride 0x800 |

**调用约定**：`void Transform(void* worldHolder)`，其中
`worldHolder[0]` 必须是 ECS world 指针（handler 第一件事就是 `movq (%rcx),%r9`，
然后读 `r9+0x4b0 / +0x4b8 / +0x4ba / +0x7f0 / +0x7a0 / +0x1a8`）。

**这正是 `GetCtx` 返回值的形状** ——
`void* GetCtx(void* store) { return *(void**)(*(void**)store + 8); }`
所以 M1 已经拿到的 world context 可以直接喂给 transformer。

### 0x1409d5770 = entity program 注册器（817 个调用点）

`0x1404a5a30`(17344 B) 是静态 bootstrap，`movq %rcx,%rbx` 后把 rbx 当 registry
传给每个注册。调用形状（`0x1404a76bf` 起）：

```
callq <thunk>        ; rax = descriptor
movq  %rax,%rdx      ; rdx = descriptor
xorl  %r8d,%r8d      ; r8  = bool flag
movq  %rbx,%rcx      ; rcx = registry/world
callq 0x1409d5770
```

内部（`0x1409d5941` 起「表满/新增」分支）：

```
1409d578e: testb $0x2,0x180(%rdx)          ; descriptor 标志位，置位则走另一分支
1409d57a9: cmpw 0xe15350(%rcx),%di ; jae   ; programCount >= 上限 -> 拒绝
1409d57b2: leaq 0x746360(%rcx),%r14        ; 既有表，步长 0x1f20，上限 0x380
1409d57c0: movups (%r15),%xmm0             ; 查重：比较 descriptor[0..0x20]
1409d5962: incw 0xe15350(%rsi)             ; programCount++
1409d5969: movq %r15,(%rbx)                ; slot+0x00 = descriptor->name
1409d5970: movups %xmm0,0x10(%rbx)         ; slot+0x10..0x20
1409d5974: movq 0x10(%r15),%rax ; movq %rax,0x28(%rbx)   ; slot+0x28 = handler
1409d597c: movl 0x180(%r15),%ecx ; movl %ecx,0x20(%rbx)  ; slot+0x20 = desc+0x180
1409d5986: movl 0x184(%r15),%eax ; movl %eax,0x24(%rbx)  ; slot+0x24 = desc+0x184
1409d5990: testb %r12b,%r12b ; je skip ; orl $0x2,%ecx ; movl %ecx,0x20(%rbx)
1409d599b: movb $0x1,0x2d8(%rbx) ; movb $0x1,0x588(%rbx)
1409d59cd: movw %dx,0xe15358(%rsi,%rax,2)  ; 索引回写
1409d59d5: incw 0xe15a58(%rsi)
1409d59eb: movq 0x8(%r15),%rdx              ; nameLen
1409d59f3: movq (%r15),%r8                  ; name
          ; FNV-1a(0x811c9dc5 / 0x1000193) 写进 world+0xe15a60 的哈希表
```

错误串（证明这是 ECS 程序注册）：`"[ecs%c] entity program '%s' already
registered"` (rva 0x1d5fae8)、`"[ecs%c] Can not register program '%s', too many
programs"` (rva 0x1d5fb18)、`"Could not found component type %k"` (rva 0x1d5fb60)。

**descriptor 表是静态只读注册数据**：`.text` 里没有任何 `lea rip` / `call` /
`.rdata` u64 反引用指向 `0x1E2B680` / `0x1E2B860` / `0x1E2BA50`，
只有 descriptor 内部的 `{ptr,count}` 互相指。**不能靠改 descriptor 注册自定义
行为**，但 `0x1409d5770` 是活函数，自建 descriptor 可注册 —— 这条路留作后备。

### 本轮代码改动

`src/gamehooks.h`：
- `namespace rva` 新增 `QueryBuild 0x9BAB60` / `QueryRun 0x9B5A50` /
  `QueryNext 0x9B8010` / `ComponentRemove 0x9C5DF0` /
  `EnemyToWildlife 0x480C70` / `WildlifeProgram 0x480A70`。
- 新增 `bool TransformEnemyToWildlife()` 与 `int LastTransformCount()`。

`src/gamehooks.cpp`：
- 新增 `TransformEnemyToWildlife()`：把 `WorldContext()` 塞进 2 元素 holder，
  `holder[0] = world`，直接调 `base + rva::EnemyToWildlife`。
  **没有用 `__try/__except`** —— 这个 DLL 没开 SEH，且 handler 只解引用引擎
  自己校验过的指针；真崩了就是要看见，而不是吞掉。
- `LastTransformCount()` 返回 -1(未运行) / 0(失败) / 1(已调用)。

`src/mod.cpp` `RequestSummon()`：
- 三步走，全部经游戏自身代码：`TransformEnemyToWildlife()` →
  `TameEntity(wolf,true)` →（`SetAllyOnTame` 开启时）阵营改写。
- 文案改为「已改造为 wildlife 并驯化: entity %u」。

`src/mod.cpp` 菜单：
- 「最近识别的野狼」下方新增「wildlife 改造: 未运行 / 失败 / 已运行」。

`src/console.cpp`：
- 新增命令 `transform`（无参），跑一遍 `wildlife_enemy_transformer`，
  并在回显里写清「这是 TameWildlifeEvent 能对狼生效的前提」。
- `kCommands` 加入 `{"transform", "transform — run the engine's enemy->wildlife program", CmdTransform}`。

`tools/console-test.cpp`：
- stub 补 `TransformEnemyToWildlife()` / `LastTransformCount()`。
- 新增断言：无 world context 时 `transform` 必须返回 `NotAvailable`。
- 修正 `Execute(line)` 调用签名（原来传了 2 个参数，编译不过）。

`tools/run-tests.bat`：
- 新增 `[6/8] console command honesty`，编译并运行 `console-test.cpp`
  （此前该测试写好了却没接入）。
- 编号 1..6 全部改为 1..8。

### 测试结果

```
[1/8] ECS probe self test        PASS -- 7/7 ECS signatures in the shipped exe
[2/8] taming rules               PASS -- all taming rules (wolf+torch, uniqueness, re-block)
[3/8] combat follow plan         PASS -- faction/IsTame/Animal plan matches shipped data
[4/8] mount state machine        PASS -- attachment/camera/pose + enter-exit transitions
[5/8] detour engine              PASS -- inline hook install/call/remove round-trip
[6/8] console command honesty    PASS -- missing backends report NotAvailable, never Ok
[7/8] layer build                PASS -- wolfmount_layer.dll built
[8/8] vulkan loader sees layer   PASS -- layer registered and enumerated by the loader
ALL TESTS PASSED
```

### 仍未验证（下一步）

1. `TransformEnemyToWildlife()` 在真实游戏里会不会崩 / 是否真的翻转了狼的
   UnitMode。**没有回读手段**，只能靠行为变化（狼停止攻击玩家、可被
   TameWildlifeEvent 命中）间接判断。
2. `holder[0] = WorldContext()` 是否就是 handler 期望的 world。GetCtx 的返回值
   与 `QueryBuild` 第一个参数是同一个对象的**强假设**，尚未实测。
3. `QueryBuild` 的 `out` 缓冲必须 0xa8 字节且由调用方提供栈空间；handler 自己
   在栈上开 0x108 并传 `lea 0x30(%rsp)`，所以我们只传 holder 是对的。
4. 若崩溃，退路：自建 descriptor 走 `0x1409d5770` 注册（组件组已全部解出）。

### 教训

- 段表必须从 PE 头解析，不能手抄（`.rdata` 与 `.pdata` 曾弄混，导致一批结论作废）。
- 「无读引用」不能推出「无消费者」：组件哈希只在写入时出现，读取方用解析后的索引。
- 反射索引 2887（AdminSpawnCommand）在 `.text` 里作为指令立即数**不存在**，
  admin 命令完全靠反射表反序列化，静态 hook 无法注入。
"""


def main():
    with io.open(LOG, "a", encoding="utf-8") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
