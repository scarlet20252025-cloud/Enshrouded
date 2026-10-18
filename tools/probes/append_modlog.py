r"""Append the behaviour-descriptor / program-registry findings to MODLOG.md.

Findings this round (all verified against enshrouded.exe via tools/):

1. 16 "behaviour descriptor" records in .rdata, reached ONLY through 16
   8-byte `lea rax,[rip+d]; ret` thunks at .text rva 0x12cf5c0 (stride 0x10).
2. Descriptor layout: +0x00 char* name, +0x08 u64 nameLen, +0x10 void* handler,
   +0x18.. {char** pool; u32 count} groups (a {0,0} pair is a VALID empty group;
   the list ends at the first pair where BOTH this and the next are {0,0}).
3. The flat component-name pool is 16 bytes per entry {char*, u32 len, u32 pad},
   spanning rva 0x1e2b400..0x1e2b690.
4. wildlife_enemy_transformer (descriptor rva 0x1e2b860, handler rva 0x480c70)
   groups: ['IsTame'] and ['DynamicEnemy01BehaviorState','UnitTransformer',
   'WildlifeTransformer'] — plus THREE EMPTY groups at +0x18/+0x28/+0x38.
5. wildlife_farm_animal_transformer (descriptor rva 0x1e2ba50, handler 0x481060)
   groups: ['Wildlife'], EMPTY, ['DynamicWildlife'], ['IsTame'],
   ['DismantleOverride','Faction'].
6. 0x1409d5770 is the ECS "entity program" registrar:
   void Register(void* ecsWorld, void* descriptor, bool flag)
   - rejects duplicates by comparing descriptor[0..0x20] against the existing
     table at world+0x746360 (stride 0x1f20, max 0x380 entries)
   - on success: memset(world+0x746350 + idx*0x1f20, 0, 0x1f20), then copies
     descriptor+0x00..0x28 into slot+0x00..0x28, copies descriptor+0x180/+0x184
     into slot+0x20/+0x24, ORs 2 into slot+0x20 when flag!=0, sets slot+0x2d8=1,
     slot+0x588=1, slot+0x8 = new u16 index, and FNV-1a hashes the descriptor
     NAME into the component-type hash table (0x811c9dc5 / 0x1000193 inline).
   - error strings: "[ecs%c] entity program '%s' already registered",
     "[ecs%c] Can not register program '%s', too many programs"
7. 0x1404a5a30 (17344 B) is the static bootstrap that registers ~800 programs;
   it is called from 0x14039fbb0 (10432 B) and 0x1404949b0 (17209 B).
"""
import io
import os

MODLOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "MODLOG.md")

TEXT = """
---

## 2026-10-17 — 行为描述符表（entity program registry）完整解码

**这是本轮最重要的发现**：游戏有 16 个「行为描述符」，全部通过 `.text`
rva `0x12cf5c0` 起、步长 16 字节的 8 字节 thunk（`48 8D 05 <rel32> C3` +
int3 填充）暴露。**每个 thunk 只有 1 个调用者**，全部集中在两个大函数里：

| thunk rva | descriptor rva | 名字 | handler rva | 调用者函数 |
|---|---|---|---|---|
| 0x12cf5c0 | 0x1e2a820 | extinguish_client | 0x47c250 | 0x4a5a30 (17344 B) |
| 0x12cf5d0 | 0x1e2a9e0 | water_dispenser_client_init | 0x47c960 | 0x4a5a30 |
| 0x12cf5e0 | 0x1e2abb0 | water_dispenser_server_init | 0x47caa0 | 0x4a5a30 |
| 0x12cf5f0 | 0x1e2ad80 | water_dispenser_server_toggle | 0x47cc00 | 0x4a5a30 |
| 0x12cf600 | 0x1e2af50 | water_drain_server_init | 0x47cd90 | 0x4a5a30 |
| 0x12cf610 | 0x1e2b120 | water_drain_server_toggle | 0x47ce50 | 0x4a5a30 |
| **0x12cf620** | **0x1e2b680** | **wildlife** | **0x480a70** | 0x4a5a30 |
| **0x12cf630** | **0x1e2b860** | **wildlife_enemy_transformer** | **0x480c70** | 0x4a5a30 |
| **0x12cf640** | **0x1e2ba50** | **wildlife_farm_animal_transformer** | **0x481060** | 0x4a5a30 |
| 0x12cf650 | 0x1e2bc70 | allyaggromultiplier_init | 0x122c6e0 | 0x122c1c0 (1304 B) |
| 0x12cf660 | 0x1e2be20 | armor_init | 0x122c7d0 | 0x122c1c0 |
| 0x12cf670 | 0x1e2bfd0 | armorpoints_init | 0x122c8c0 | 0x122c1c0 |
| 0x12cf680 | 0x1e2c180 | block_init | 0x122c9b0 | 0x122c1c0 |
| 0x12cf690 | 0x1e2c330 | bodyheat_init | 0x122caa0 | 0x122c1c0 |
| 0x12cf6a0 | 0x1e2c4e0 | bodyheatmaxmod_init | 0x122cb90 | 0x122c1c0 |
| 0x12cf6b0 | 0x1e2c690 | comfort_init | 0x122cc80 | 0x122c1c0 |

`0x1404a5a30` 自身只有 2 个调用者：`0x14039fbb0`(10432 B) 与
`0x1404949b0`(17209 B)。

### Descriptor 结构（变长，无固定 stride；相邻间距 0x1b0–0x220 不等）

```
+0x00  char*  name
+0x08  u64    nameLen
+0x10  void*  handler
+0x18  ...    {char** pool; u32 count} 组，直到「本组与下一组都为 {0,0}」为止
```

**坑**：`{0,0}` 是**合法的空组**，不是终止符。`wildlife_enemy_transformer`
前 3 组全是 `{0,0}`。

组件名池是扁平 16 字节条目 `{char* name; u32 len; u32 pad}`，范围
`rva 0x1e2b400 .. 0x1e2b690`。

### 两个 transformer 的组件组（直接决定狼能不能被改造）

```
wildlife_enemy_transformer  (descriptor 0x1e2b860, handler 0x480c70)
    group0  EMPTY
    group1  EMPTY
    group2  EMPTY
    group3  rva=0x1e2b808 n=1: IsTame
    group4  rva=0x1e2b818 n=3: DynamicEnemy01BehaviorState, UnitTransformer, WildlifeTransformer

wildlife_farm_animal_transformer  (descriptor 0x1e2ba50, handler 0x481060)
    group0  rva=0x1e2b9e8 n=1: Wildlife
    group1  EMPTY
    group2  rva=0x1e2b9f8 n=1: DynamicWildlife
    group3  rva=0x1e2ba08 n=1: IsTame
    group4  rva=0x1e2ba18 n=2: DismantleOverride, Faction
```

`wildlife` (descriptor 0x1e2b680, handler 0x480a70) 的组最全：
`FleeSensor / MovementColliderConfig / PathWalker / Wildlife`、
`FlyingEnemy`、`CurrentTransform / DynamicHitReactionBehavior / MovementCollider`、
`DynamicFlying / IsTame / UnitTransformer`、
`Actor / ActorInput / DynamicFleeSensor / DynamicLocomotion /
DynamicNetworkLocomotion / DynamicPathWalker / ServerAnimationGraphInput /
SteeringAgent / DynamicWildlife`、
`NetworkWildlife / SteeringBehavior_Separation / DynamicSteeringLocomotion`。

### 0x1409d5770 = ECS「entity program」注册器（817 个调用点）

签名（从 `0x1404a76bf` 处的调用序列反推）：

```
callq <thunk>      ; rax = descriptor
movq  %rax,%rdx    ; rdx = descriptor
xorl  %r8d,%r8d    ; r8  = bool flag
movq  %rbx,%rcx    ; rcx = ecs world/registry
callq 0x1409d5770
```

即 `bool Register(void* world, void* descriptor, bool flag)`。

内部行为（`0x1409d5941` 起的「表满/新增」分支，字节级）：

```
; 查重：比较 descriptor[0..0x20] 与 world+0x746360 起、步长 0x1f20、
;       上限 0x380 条的既有表
imulq $0x1f20,%rax,%rbx ; addq $0x746350,%rbx ; addq %rsi,%rbx
callq 0x1413aba00        ; memset(slot, 0, 0x1f20)
incw  0xe15350(%rsi)     ; world->programCount++
movq  %r15,(%rbx)        ; slot+0x00 = descriptor->name
movups (%r15),%xmm0 ; movups %xmm0,0x10(%rbx)   ; slot+0x10..0x20
movq  0x10(%r15),%rax ; movq %rax,0x28(%rbx)     ; slot+0x28 = descriptor->handler
movl  0x180(%r15),%ecx ; movl %ecx,0x20(%rbx)    ; slot+0x20 = descriptor+0x180
movl  0x184(%r15),%eax ; movl %eax,0x24(%rbx)    ; slot+0x24 = descriptor+0x184
testb %r12b,%r12b ; je skip ; orl $0x2,%ecx ; movl %ecx,0x20(%rbx)
movb $0x1,0x2d8(%rbx) ; movb $0x1,0x588(%rbx)
movzwl 0xe15350(%rsi),%edx ; movw %dx,0x8(%rbx)  ; slot+0x8 = index
; FNV-1a over descriptor->name -> 写进 world+0xe15a88 的哈希表
movl $0x811c9dc5,%ebx ; imull $0x1000193,%eax,%ebx
```

错误串（证明这是 ECS 程序注册）：
`"[ecs%c] entity program '%s' already registered"` (rva 0x1d5fae8)、
`"[ecs%c] Can not register program '%s', too many programs"` (rva 0x1d5fb18)、
`"Could not found component type %k"` (rva 0x1d5fb60)。

### 对模组的含义

- **descriptor 表是静态只读注册数据**：`.text` 里没有任何 `lea rip` /
  `call` / `.rdata` u64 反引用指向 `0x1e2b680` / `0x1e2b860` / `0x1e2ba50`，
  只有 descriptor 内部的 `{ptr,count}` 互相指。**不能靠改 descriptor 注册自定义行为。**
- 但 `0x1409d5770` 是**活的注册函数**：如果我们能把一个自建 descriptor
  （名字 + handler + 组件组）喂给它，就能让游戏在运行时新增一个 entity program。
  这需要先拿到 `world`（`rcx`）—— 与 `GetCtx 0x1409B0860` hook 已拿到的
  world context 是否是同一个对象，**尚未验证**。
- `wildlife_enemy_transformer` 的 handler `0x140480c70` 就是「把 Enemy 原地
  改造成 Wildlife」的原生实现，它调用 `0x1409bab60`(查询, out=0xa8 字节) →
  `0x1409b5a50`(消费) → 遍历实体 → `0x1409b2e40`(ResolveEnt) → 命中后
  `0x1409c5df0`(疑似组件移除) 并**就地翻转 `buffer+0x40` 处的 UnitTransformer
  模式字节**（`movb $0x1,(%rax)` / `movb $0x0,(%rax)`，对应
  `keen::ecs::UnitMode{Wildlife=0, Enemy=1}`）。
  调用约定：`void Transform(void* world, void* outBuf0xa8, ...)`。
"""


def main():
    with io.open(MODLOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
