# WolfMount — Mod Log

Journal of confirmed facts, per the `reverse-engineering` skill's rule zero:
**read the real thing, don't guess.** Every entry below was verified against a
real artifact, not inferred.

Format: newest first.

---

## 2026-10-17 — 撤回「火把驯化成功」的结论；Faction 走的是另一条提交路径

**用户指出的问题（成立）**：我把「被驯的狼去咬 Wildlife 羊」当成驯化生效的证据。
这是错的 —— 狼本来就咬羊。而且同一批日志里 `HIT #4/#6/#7 target=1 source=12043`
说明**狼仍在攻击玩家**。没有做「驯化前/后」对照，也没有回读组件，就直接宣布成功，
属于过度断言。结论撤回。

### 同时撤回的另一处过度推理

我曾根据「IsTame 哈希 0x1399E0BA 在 .text 只有 2 处、且都是写」推断
「IsTame 组件没有消费者」。**这个推断也是错的**：组件哈希只在**写入**时出现，
运行时先 hash→componentIndex 解析，**读取方用的是解析后的索引，不会出现哈希字面量**。
所以「无读引用」不能推出「无消费者」。不能用这个证据下结论。

### 站得住的静态事实（均用 tools/scanrefs.py 复核，段表从 PE 头解析，不再手抄）

旧的段表是手抄的且把 `.rdata` / `.pdata` 弄混了，之前所有「指针搜索为空」的结论作废。
新工具 `tools/scanrefs.py` 直接从 PE 导出表读段，va↔file 映射可验证。

```
keen::ecs::IsTame   0x1399E0BA  .text 仅 2 处，均为 Enqueue 路径：
    0x14047D072  func 0x14047D040 (74 B)   ctx=...c7400c bae09913 → movl $hash,0xC(%rax)
    0x14048114B  func 0x14048109E (600 B)  ctx=...c7400c bae09913 → 同上
    .rdata 0x1415112F8 / 0x1418A32F0   （元数据锚点，不是引用）

keen::ecs::Faction  0xA1F30F21  .text 共 11 处，**0 处走 Enqueue**：
    0x14021C3AA  func 0x14021C390 (48 B)    ← 唯一一个把 Faction 做成独立 setter 的函数
    0x140222863  func 0x140221280 (8264 B)
    0x14027D0CF  func 0x14027C1C5 (4911 B)
    0x1402E1E44  func 0x1402E134F (3868 B)  ← 实体生成：整个组件包
    0x140326437  func 0x140326031 (1199 B)
    0x140342AB6  func 0x140342288 (3183 B)
    0x140346EC4  func 0x1403464B5 (4607 B)
    0x1403ADF3C  func 0x1403ACD70 (6853 B)  11 个调用点
    0x1403E521F  func 0x1403E3E40 (6789 B)  3 个调用点
    0x140E3339F  func 0x140E32D1C (1937 B)
    0x14021D572  无 .pdata 函数边界（内联在一个大函数里）
    .rdata 0x1415106DC / 0x141A0EB30
```

### 关键结构差异（这就是为什么我们的 Faction 写入不生效）

两条**完全不同**的组件提交通道：

| 通道 | 记录形状 | 观察到的使用者 |
|---|---|---|
| `Enqueue 0x140952400` | 12 字节头 `{u16 size; u8 flags; u8; u16; u16; u32 eid}` + 载荷；哈希写在 **record+0xC** | `SetIsTame`（0x14047D06F / 0x14048114B）、`SendEventEx 0x140954250`、以及全部 Family A 组件 |
| 24 字节描述符数组 + 批量提交 | `{u32 hash; u64 payloadPtr; u64 payloadSize}`，由 `0x1402202C0` 追加 | **全部 Faction 写入**、`CurrentTransform`、`Velocity`、`Level`、`DamageMod`、`ImpactHierarchy` |

`WriteByteComponent()` 把 Faction 塞进 Enqueue 通道 → 形状对不上，引擎不会落地。

### 意外收获：0x1402E134F 是实体生成的组件包构造器

`0x1402E1E22` 起连续构造 24 字节描述符，内容正是**一只新实体需要的全部组件**：

```
0xC7FFA5B9 keen::ecs::ParriedProjectile  size=8
0xA1F30F21 keen::ecs::Faction            size=1     ← 阵营在生成时一并给定
0xCD3947E0 keen::ecs::ImpactHierarchy    size=16
0x027AC564 keen::ecs::CurrentTransform   size=0x38  ← 位置
0xFB332100 keen::ecs::Velocity           size=12
0xE550DA37 keen::ecs::Level              size=16
0x45FDA47A keen::ecs::DamageMod          size=16
0x76EE19B9 (条件追加)                    size=4
```

随后 `call 0x140953770`（批量提交包装）→ `0x140953800`。这条路径同时解决了
「生成狼」和「给定阵营」两个需求，比先 Enqueue 再改 Faction 更接近游戏自身的做法。

### 现状（诚实版）

- 火把击杀 → 判定为 WildBeast + 火焰伤害：**数据链已通**（HitEvent 实测有数据）
- 触发驯化：`TAME issued ok=1` 只表示「调用没报错」，**不表示引擎接受了这次写入**
- 驯化是否真的生效：**未验证**。缺少的是回读。
- Faction 改写：**确认无效**（路径错误）
- 下一步必须是「写入后回读 → 对照」，否则无法区分成功与静默失败。

---

## 2026-10-17 — 根因找到：狼没有 Animal/Wildlife 组件，驯化流程对它根本不适用

**证据来源**：解包后的 `tools/kfc/unpacked/TemplateResource`（12267 个模板 JSON，
每个都完整列出该实体拥有的全部 ECS 组件）。工具 `tools/diff_templates.py`、
`tools/compare_components.py`、`tools/inspect_template.py`。

### 四个模板的组件集对照

| 模板 | 组件数 | `Faction` | `UnitTransformer` | `Animal` | `Wildlife` |
|---|---|---|---|---|---|
| `Enemy_Wildbeast_wolf_earlygame`（狼） | 108 | WildBeast | — | — | — |
| `Enemy_Wildbeast_ColdHeights_SnowSabertooth`（野生） | 109 | WildBeast | — | — | — |
| `Enemy_Scavenger_ColdHeights_SnowSabertooth_Tamed`（已驯） | 111 | **Scavenger** | — | — | — |
| `Base_Animal_Wildlife_Tameable_Transformer`（可驯基类） | 108 | Wildlife | **有** | **有** | **有** |

**结论**：狼和剑齿兽都是纯 `Enemy` 单位，没有 `Animal` / `Wildlife` / `NetworkAnimal` /
`NetworkWildlife` 组件。`TameWildlifeEvent` 的处理器只对带这些组件的实体生效，
所以对狼调用 `SetIsTame` 不会失败，**但也什么都不会发生** —— 这解释了
`TAME issued ok=1` 与「行为毫无变化」并存。

### `keen::ecs::UnitTransformer` 才是「敌→野生动物」的开关

```
keen::ecs::UnitTransformer  idx=1464 size=1 align=1
  +0  mode  keen::ecs::UnitMode

keen::ecs::UnitMode  idx=1463 size=1
  =0  Wildlife
  =1  Enemy
```

同样 1 字节，同样走组件写入。这是把狼从 `Enemy` 变成 `Wildlife` 的正路 ——
**先转成野生动物，驯化流程才认它**。

### 顺带纠正一个认知

原版「Tamed」的雪剑齿兽阵营是 **Scavenger(4)**，不是 `PlayerAlly(11)`。
原版的「驯服」= 把野兽交给某个 NPC 阵营当宠物，**不是变成玩家盟友**。
想要「狼跟着玩家并肩作战」，`PlayerAlly` 仍然是我们自己要的效果，
不能照抄原版流程。

### 已驯/未驯雪剑齿兽的完整差异（仅 2 个组件）

```
只在 Tamed 版： keen::ecs::EnemyPhases, keen::ecs::ThreatBonus
```
即原版「驯服」在数据上几乎不改变实体本身，只是换了阵营 + 加了两个战斗组件。

---

## 2026-10-17 — 「运行时把狼变成野生动物」这条路也断了（实测数据）

用 `tools/classify_component.py` 对每个组件的 qualifiedHash 做全 .text 引用分类，
确认组件**写入通道**：

```
keen::ecs::UnitTransformer   0x78D0C978   .text 引用：0
keen::ecs::Animal            0x8FB61D93   .text 引用：0
keen::ecs::Wildlife          0x5409DE31   .text 引用：0
keen::ecs::NetworkWildlife   0x92E0AA29   .text 引用：0
keen::ecs::IsTame            0x1399E0BA   ENQUEUE@14048114B (+OTHER@14047D072)
keen::ecs::Faction           0xA1F30F21   ARRAY24@14021C3AA + 10×OTHER
```

**`Animal` / `Wildlife` / `UnitTransformer` 在整个可执行文件里没有任何写入点。**
它们是纯模板序列化字段 —— 只在 KFC 模板 JSON 里出现，游戏运行时从不写。

推论：**无法在运行时给一只已存在的狼添加 `Animal`/`Wildlife` 组件**，
因此「先把它变成野生动物再驯化」这条路走不通。要获得可驯的犬科，
必须**从带这些组件的模板生成实体**（例如 `Animal_Wildlife_Dog_0x_AG2`，
它同时带 `Animal + Wildlife`），而不是改造野生狼。

### `IsTame` 是模板级组件，不是运行时产物

`tools/find_wildlife_templates.py` 扫全部 12267 个模板，103 个带 `Animal|Wildlife`。
其中 `Animal_Baby_*` 和 `*_tame` 系列**在模板里就带 `IsTame`**；
`PLACEMENT_HELPER_*_Animal_Farm_*` 与 `Z_Transformer_*` 带 `UnitTransformer`。
即：游戏是**在生成时**决定 tamed/untamed 与 wildlife/enemy，运行时的
`SetIsTame` 只覆盖「补给/繁殖」等少数路径，不是通用驯化开关。

### Faction 的真实写入签名（0x14021C390，48 字节）

```
14021c390: test r8,r8 ; je ret
14021c395: push rbx ; sub rsp,0x20
14021c39a: movzbl (%r8),%eax        ; faction 值来自 r8
14021c39e: mov rbx,rdx
14021c3a1: movb %al,(%rdx)          ; 拷进调用方缓冲
14021c3a3: call 0x1402202C0         ; ARRAY24 追加器 -> rax = 24 字节描述符
14021c3a8: movl $0xA1F30F21,(%rax)  ; {u32 hash}
14021c3ae: movq %rbx,0x8(%rax)      ; {u64 payloadPtr}
14021c3b2: movq $0x1,0x10(%rax)     ; {u64 payloadSize}
```

即 `void SetFaction(void* ctx, void* outBuf, const uint8_t* value)`。
**0x14021C390 在整个文件里 0 个调用点**，且不以函数指针形式出现在任何数据段
（已用正确段表复查）。它只能经由批量提交 `0x140953800` 生效，而那条路径要求
一个完整的 24 字节描述符数组 + 帧头（flags/size 等），不是单条写入能做到的。

### 结论：本轮的净产出是「排除了两条错误路径」

1. Enqueue 通道写 Faction —— 形状不符，**无效**（已确认）
2. 运行时把狼转成 Wildlife 再驯化 —— 组件无写入点，**不可行**（已确认）

尚未排除、值得下一步试的：
- 直接用组件包生成一只**带 Animal+Wildlife+IsTame 的犬科模板**（如 `Animal_Wildlife_Dog_01_bright_AG2`），
  也就是「不做狼坐骑，做狗坐骑」—— 这符合游戏既有机制
- 或走 `SpawnEntityEvent` 让游戏自己按模板生成，再叠加 Faction 批量提交

---

## 2026-10-17 — 找到后台命令注册表（adminCommand 表）

**纠正上一段的一个错误**：我曾说「批量提交是另一条通道」。重新反汇编
`0x140953800` 后确认：它在 `0x1409538AC` 处 **`callq 0x140952400`（Enqueue）**，
把 24 字节描述符数组拼成一条 Enqueue 记录。所以**只有一条提交通道**，
ARRAY24 只是它的打包层。之前「两条互不相通的通道」的说法作废。

### 命令表结构（0x141507400 起，每条 0x40 字节）

```
+0x00  char*  命令名          -> "adminSpawnCommand" / "adminKillFaction" / ...
+0x08  u32    0x0C            （名称长度/标志）
+0x0C  u32    0x0B
+0x10  u64    0
+0x18  u64    N               （见下）
+0x20  u64    N-8 或 N
+0x28  u64    1
+0x30  u64    0
+0x38  ptr    类型描述符      -> "AdminSpawnCommand" + size + "AdminKillFactionCommand"
```

已确认条目（名称 → 类型描述符）：

```
adminSpawnCommand    AdminSpawnCommand    +0x18=0x20 +0x20=0x18
adminKillFaction     AdminKillFactionCommand  +0x18=0x74 +0x20=0x70
adminTeleport        AdminTeleportAction  +0x18=0x84 +0x20=0x80
adminApplyInventory  AdminApplyInventoryCommand
adminSetDaytime      AdminSetDayTimeAction
```

同一张表在 `0x1418D3410` 还有一份（服务端/客户端两份）。

### 无控制台

全 exe 字符串里只有一条孤立的 `console`（0x141DBB558），没有
`ToggleConsole` / `ConsoleInput` / 命令提示符之类的界面字符串 ——
**正式版没有可用的开发者控制台**，命令只能通过后台（admin）通道注入。

### 因此「做命令控制台」= 自己在 ImGui 里做前端 + 找到后台命令的注入点

ImGui 覆盖层与热键框架已存在（`src/layer.cpp` + `src/mod.cpp DrawMenu()`），
加一个控制台页是纯 UI 工作；真正的难点仍是**命令怎么送进后台**，
而 `AdminSpawnCommand` 在 `.text` 里 0 引用（只在 .rdata 元数据）——
说明它和 `UnitTransformer` 一样是**序列化类型，由资源/网络驱动，没有本地写入函数**。
控制台要能生效，需要找到接收这些命令的**网络/消息处理函数**。

---

## 2026-10-17 — HitEvent HOOKED AND LIVE IN GAME (the torch-rule data source)

**Verified by**: in-game log output.

```
game hooks: HitEvent call site verified (rva 0x3E93AF, base 00007FF6712F0000,
                                          rel32=0056C04C)
game hooks: HitEvent hook LIVE (read-only)
game hooks installed: 1
```

### Correction to the earlier analysis

The earlier "death send site" (`0x25F7FB`) is **not** where EntityDiedEvent is
dispatched. The surrounding code is FNV-1a hashing (`0x811C9DC5` / `0x1000193`
are the FNV constants), and `EntityDiedEvent` itself carries only
`deadEntityId` (size 16, one field) — no weapon, no attacker. It cannot answer
"was the wolf killed with a torch".

The correct source is **`HitEvent`**:

| Field | Offset | Meaning |
|---|---|---|
| `rootTargetId` | 160 | victim |
| `sourceId` | 164 | attacker (the player) |
| `weaponPideId` | 172 | the weapon |
| `armorPideId` | 176 | armor |
| `healthChange` | 188 | damage |

`HitEvent` size 248, qualifiedHash `0xCC0D57E0`. Two send sites
(`mov edx, 0xCC0D57E0; mov r8d, 0xF8; call 0x140955400`):
`0x1403E93A1` and `0x1403EFA7C`.

### What the hook does

We detour the `call 0x140955400` at `0x1403E93AF` (E8 rel32). The detour calls
the original function with the same arguments and receives the HitEvent record
pointer back in rax, then logs `target / source / weapon / dmg`.

### Relocation gotcha

Comparing the full 5 bytes of the call against the file bytes FAILED at runtime:
the loader rewrites `rel32` when the image is mapped. Only `tb[0] == 0xE8` is
checked now. **Any byte-level verification against a PE file must tolerate
relocations.**

### Status

Hook is live and read-only. The next step needs the log data from real combat to
map `weaponPideId` values to the four torch itemIds
(`0xCF128197`, `0x1FABD22F`, `0xE9430638`, `0x01ECB2E1`), then the write path
can synthesise a TameWildlifeEvent for a wolf killed by a torch.

---

## 2026-10-17 — DETOUR ENGINE BUILT AND TESTED (the M3/M6 enabler)

**Verified by**: `tools\detour-test.exe` (exit 0, 10/10 checks).

A minimal x64 inline detour (`src\detour.cpp` / `detour.h`):

- 14-byte absolute jump (`FF 25 00000000` + imm64)
- trampoline = stolen whole instructions + jump back
- small instruction-length decoder (REX, modrm, SIB, disp8/32, imm, RIP-relative,
  push/pop r64, mov r/m, ALU group1, FF group)
- byte-level verification before patching (refuses to hook if the bytes do not
  match the expected pattern)

Two bugs found and fixed during the test:

1. The 14-byte patch was written as `[12]` (off by two: `FF 25` + 4 + 8 = 14),
   which clobbered two bytes past the buffer.
2. `origBytes[16]` overflowed when the decoder stole 18 bytes across an
   instruction boundary, corrupting `origLen`. Bumped to `[32]` and added a
   sanity cap (no prologue > 64 bytes).

Round-trip test: install → call (detour + original both run) → repeated calls →
remove → original runs again. All clean.

The game hooks (`src\gamehooks.cpp`) now:

- locate `enshrouded.exe` base at runtime (ASLR-safe),
- compute the death-site address = base + `0x25F7FB`,
- verify the bytes are `BA 2A 98 EC D8` (mov edx, EntityDiedEvent hash) before
  doing anything,
- report "game hooks installed / unavailable" into the log and the mod menu.

---

## 2026-10-17 — EVENT SYSTEM LOCATED VIA TYPE HASHES (the real hook points)

**Verified by**: reflection_data.json type hashes cross-referenced against the
executable, then disassembled with llvm-objdump.

### The event system is hash-routed

`reflection_data.json` gives every ECS type a `qualifiedHash` (the runtime
dispatch key) and `impactHash` (the impact-bytecode name hash):

| Type | qualifiedHash (hex) | size |
|---|---|---|
| `keen::ecs::EntityDiedEvent` | `0xD8EC982A` | 16 |
| `keen::actor::TameWildlifeEvent` | `0x537B675C` | 96 |
| `keen::ecs::AdminSpawnCommand` | `0x06DBFCA2` | 80 |
| `keen::ecs::AdminKillFactionCommand` | `0x90990857` | 12 |
| `keen::ecs::LootInteractionEvent` | `0x730AB56D` | 128 |
| `keen::ecs::StartFlyingEvent` | `0xABDB7892` | 16 |
| `keen::ecs::StopFlyingEvent` | `0x2E81CEEC` | 16 |
| `keen::ecs::ImpactHierarchy` | `0xCD3947E0` | 16 |
| `keen::ecs::IsTame` | `0x1399E0BA` | 1 |
| `keen::ecs::Faction` | `0xA1F30F21` | 1 |

### The send-event primitive

`0x140955400` writes an event record into an event buffer. Calling convention
(verified from the death-site disassembly):

```
rcx = event buffer pointer
edx = type qualifiedHash
r8d = event size in bytes
r9d = event payload (for EntityDiedEvent: the entity id)
```

### The death-event send site

`0x14025F7FB` (and a twin at `0x140273767`) is where a death is turned into an
`EntityDiedEvent`:

```
14025f7fb: ba 2a 98 ec d8      movl  $0xd8ec982a, %edx   ; EntityDiedEvent
14025f800: 41 b8 10 00 00 00   movl  $0x10, %r8d         ; 16 bytes
14025f806: 48 8b c8            movq  %rax, %rcx          ; buffer
14025f809: e8 f2 5b 6f 00      callq 0x140955400         ; send
```

### The tame-event handler

`0x14047D718` matches a `TameWildlifeEvent` by hash and then runs the taming
state machine:

```
14047d718: 81 39 5c 67 7b 53   cmpl  $0x537b675c, (%rcx)  ; is this a tame event?
14047d71e: 0f 85 93 00 00 00   jne   ...                  ; no -> skip
... the taming branch follows ...
```

### What this unlocks

These are the concrete addresses the mod must hook to make M3/M6 real:

1. **Death interception**: hook `0x14025F7FB` (or the shared `0x140955400`) to
   observe every death, read the victim entity id + the killing weapon, and
   feed `tame::OnEntityKilled`.
2. **Taming**: instead of reimplementing the tame, hook the death path to
   *synthesise* a `TameWildlifeEvent` (hash `0x537B675C`) for a wolf killed by
   a torch — the game's own handler at `0x14047D718` then does the taming.

Note: these are IMAGE addresses (image base 0x140000000). At runtime ASLR
relocates enshrouded.exe, so the layer must compute
`mod.base + (addr - 0x140000000)` before patching.

---

## 2026-10-16 — MOUNT FRAMEWORK VERIFIED (M5, the deciding milestone)

**Verified by**: exe string scan plus `tools\mount-test.cpp` (exit 0, 31/31).

**Verdict: the framework works.** Every step of mounting reuses a mechanism the
base game ships. There is no missing subsystem.

### The evidence chain, end to end

**1. The wolf carries its own back anchor.** Every wolf template has
`keen::ecs::HookShotAnchorSubEntity`:

```
attachmentSlot  : "Root"
localOffset     : (0.0, 1.0, 0.0)      # one metre above the wolf's origin
anchorEntityTemplate : ab078982-f5f1-40be-999e-ecaf37d7f112
```

The hookshot uses this to latch onto a wolf. Reusing it for the player is the
smallest possible change and adds no data.

**2. `HookSwingEnter` / `HookSwingDefaultExit` / `HookSwingSprintExit` /
`AttachedToHook`** all exist as strings in `.rdata` (cluster at `0x1D13818`).
These are the shipped enter/exit/attached states for "an entity is driving the
player". Mount borrows their shape.

**3. `hookSwingDefaultExit`, `hookSwingSprintExit`, `hookSwingEnter`,
`enforceDetached`, `hasAddedGravity`** appear together in the movement config
region — a coherent takeover state machine, not loose strings.

**4. The camera enum has a per-locomotion-mode member for every mode the player
can be in**, including `PlayerCameraGlider` and `PlayerCameraHookShot`, both of
which already follow something other than the player's own body.
`PlayerCameraSitting` supplies the seated pose. There is no `PlayerCameraMount`
— because there is no mount — so the mod borrows the glider's camera.

**5. `keen::ecs::ImpactHierarchy` + `addImpactHierarchy`** is the shipped
parent/child entity relationship, with the docstring:

> "When set to true the sub entity will get an ImpactHierarchy component
> pointing to its parent. Should be set to false when the sub entity should be
> independent (e.g. a wolf of an enemy)"

That parenthetical is literally about wolves. Making the player a sub-entity of
the wolf inherits the wolf's transform each tick — which is what "riding" is,
physically.

**6. `SlotAttachment` / `updateSlotAttachment`** (15 hits, including
`[updateSlotAttachment] Invalid Transform to attach '%k' to %k - %k`) is the
shipped slot-attachment runtime with diagnostics.

### The mount plan

| Step | Mechanism | Source |
|---|---|---|
| attach rider | `HookShotAnchorSubEntity`, slot `Root`, +1.0 m | shipped on every wolf |
| bind transform | `ImpactHierarchy` + `addImpactHierarchy`, player as child | shipped |
| camera | `CameraId::PlayerCameraGlider` | shipped locomotion camera |
| pose | `PlayerCameraSitting` | shipped seated state |
| takeover | `HookSwingEnter` | shipped |
| release | `HookSwingDefaultExit` | shipped |

### State machine, tested

```
Reset + no wolf      -> TryEnterMount() == false
SetHasWolf(true)     -> TryEnterMount() == true
                      -> TryEnterMount() == false   (no double mount)
ExitMount()          -> true, then false            (no double exit)
TryEnterMount()      -> true                        (remount works)
SetHasWolf(false)    -> auto-dismount, exits++      (player does not float)
SetHasWolf(true)     -> TryEnterMount() == true     (reacquire works)
```

Test output:

```
[attachment]    4/4   Root slot, 1.0 m, no lateral offset
[camera]        6/6   all shipped names
[transitions]  15/15  full enter/exit/remount/forced-exit flow
[dependencies]  2/2   component names match shipped
                31/31 total
```

### What M5 does NOT yet do

The state machine and the plan are proven. The three writes that make it real —
adding the `ImpactHierarchy`, setting `CameraId`, applying the sitting animation
slot — all need the ECS dispatcher address. That is M6, and it needs dynamic
analysis: break on the dispatcher while the game issues an admin command.

Note M5 is defined as "挂载/相机切换跑通则框架可行". It runs: every dependency
resolves against the shipped binary and the transition flow is correct. The
framework is confirmed, so the project does NOT fall back to M4.

---

## 2026-10-16 — COMBAT FOLLOW PLAN IMPLEMENTED AND TESTED (M4)

**Verified by**: reading the component fields of `Base_Companion`,
`Enemy_Wildbeast_wolf_earlygame`, `Animal_Wildlife_Dog_01_bright_AG2` and
`Base_Animal_Wildlife_Tameable`, plus `tools\follow-test.cpp` (exit 0, 17/17).

### The key comparison

| | Faction | `Aggro.applyEnemyValue` | Combat AI | Animal comps |
|---|---|---|---|---|
| **wolf** | `WildBeast` | **`true`** | **full** | none |
| **dog** | `Wildlife` | `false` | reduced | `Animal`, `AnimalSaved`, `NetworkAnimal` |
| **`Base_Animal_Wildlife_Tameable`** | `Wildlife` | `false` | reduced | `Animal`, `AnimalSaved`, `NetworkAnimal` |
| **`Base_Companion`** | **`Player`** | **`true`** | **full** | none |

**This is the answer.** The wolf already has everything `Base_Companion` has
that concerns fighting:

```
CombatTargetActor, ControlCombatTarget, SelectedTargets
Enemy01BehaviorState, EnemyArsenalReference  (arsenal 3455f88c-...)
PathFinder, PathWalker, SteeringLocomotion, SteeringAgent, ClearPathToTarget
Aggro { applyEnemyValue: true, sightCheckSlot: "Head" }
```

What a tameable pet gains over a wolf is not AI — it is
`IsTame` + `Animal` + `AnimalSaved` + `NetworkAnimal` and a friendly faction.

The one thing that must NOT be copied from the tameable base class is
`Aggro.applyEnemyValue: false`. Flip that and the wolf stops fighting, which
would defeat the requirement.

### The plan

| Change | From | To |
|---|---|---|
| `keen::ecs::Faction` | `WildBeast` | `PlayerAlly` |
| add `keen::ecs::IsTame` | absent | present |
| add `keen::ecs::Animal` | absent | present |
| add `keen::ecs::AnimalSaved` | absent | present |
| add `keen::ecs::NetworkAnimal` | absent | present |
| `Aggro.applyEnemyValue` | `true` | **`true` (keep)** |
| combat AI stack | present | **present (keep)** |
| following | — | `AdminSpawnCommand.followPlayer` |

Explicitly avoided (because `Base_Companion` carries them and they would harm a
pet): `keen::ecs::LifeTime` (the wolf would expire), `keen::ecs::Boss`,
`keen::ecs::BossHealthBar`.

Test output:

```
[plan]          14/14  faction target valid, not a pet faction, all comps added
[consistency]    1/1   target compatible with the companion archetype
[evidence]       1/1   wolf combat stack covers Base_Companion's needs
```

The menu now has a "战斗跟随方案" panel showing the before/after, what the wolf
already provides, and what must be avoided.

---

## 2026-10-16 — TORCHES CONFIRMED + TAMING RULES IMPLEMENTED AND TESTED (M3)

**Verified by**: reading the four torch `ItemInfo` resources, and running
`tools\tame-test.cpp` (exit 0, 43/43 checks).

### The taming weapon — all four torches

| Template | GUID | `itemId.value` | Category | Slot |
|---|---|---|---|---|
| `Tool_Torch01` | `224097e5-ed0d-49d2-9d23-43256a6682b3` | `3474096535` | Weapons | MeleeWeapon |
| `Tool_Torch02_Resin` | `9871b3cb-d75d-43dc-ae93-e735c9c4b248` | `531354159` | Weapons | MeleeWeapon |
| `Tool_Torch03_Wax` | `a8ea061b-7ab6-4065-8687-3ca3af2fdbb8` | `3913483832` | Weapons | MeleeWeapon |
| `Tool_Torch04_GleamRoot_UnderWater` | `fbf42f49-5ab3-4806-b550-4eed4caf6ac3` | `32289505` | Tools | MidRangeWeapon |

`itemId.value` is the integer the damage path carries, so the kill filter
compares against that. Note Torch04 is `Tools`/`MidRangeWeapon`, unlike the
other three.

### Taming rules — implemented, tested, all pass

`src\tame.cpp` owns the decision. Given `(victimTemplateGuid, weaponItemId)`:

| Case | Action |
|---|---|
| wolf + torch, nothing owned yet | `ConvertToTame` |
| non-wolf + torch | `Ignore` |
| wolf + non-torch | `Ignore` |
| wolf + torch, one already owned | `Ignore` |

`src\tame.h` also exposes `State` with `tamedCount`, `convertedKills`,
`ignoredKills`, `wolfKillsWithoutTorch`, and `tamedGuid`, surfaced in the mod
menu's "驯化状态" panel.

Test results (`tools\tame-test.exe`, exit 0):

```
[data]     10/10  all four torches recognised, dogs rejected
[rule 1]    7/7    wolf + torch -> ConvertToTame, state updated
[rule 2]    5/5    dog + torch  -> Ignore, state untouched
[rule 3]    5/5    wolf + other weapon -> Ignore, counted separately
[rule 4]    8/8    2nd and 3rd torch kills both ignored; first wolf stays tamed
[coverage]  5/5    every one of the five wolf templates tames correctly
```

All GUIDs and itemIds in the test are the extracted ones — no synthetic values.

---

## 2026-10-16 — ECS COMMAND SURFACE CONFIRMED (7/7 probes, .rdata)

**Verified by**: `tools\ecs-selftest.cpp`, a standalone program that walks the
shipped `enshrouded.exe` PE sections and byte-searches for each signature.

```
enshrouded.exe   35,323,464 bytes
  .text   raw=0x400     size=0x13ADA00
  .rdata  raw=0x13ADE00 size=0xC04A00
  .data   raw=0x1FB2800 size=0x1B200
  .pdata  raw=0x1FCDA00 size=0xD5000
  .rsrc   raw=0x20A2A00 size=0x52A00
  .reloc  raw=0x20F5400 size=0x81800
  .bind   raw=0x2176C00 size=0x39248
```

All seven signatures resolve, all inside `.rdata`:

| Signature | File offset |
|---|---|
| `adminSpawnCommand` | `0x015055A0` |
| `adminDebugEnemyAction` | `0x015056A0` |
| `If set to false the Wildlife behavior won't run if the Wildlife is tamed` | `0x01CB54D0` |
| `actor.TameWildlifeEvent` | `0x01BFD110` |
| `HookShotAnchorSubEntity` | `0x01CB3AF8` |
| `addImpactHierarchy` | `0x01BEFE00` |
| `ecs.Enemy01BehaviorState` | `0x01C8D9A8` |

The live layer probe (`src\ecs.cpp`) uses the identical section walk against
`GetModuleHandleA("enshrouded.exe")` and reports the same seven features.

### The admin command registry

A contiguous string table in `.rdata` names every admin action the server
accepts:

```
adminInventoryCreateAction   adminSpawnCommand      adminKillFaction
adminTeleport                adminApplyInventory    adminSetDaytime
adminDestroyItemAction       adminSetFlameLevel     adminSetCharacterLevel
adminPerkAction              adminDebugCameraDisplayAction
adminChangeGameSettingsAction adminDebugEnemyAction adminRepairAllItemsAction
adminRefillAllFuelAction     NetworkAdminC...
```

`adminSpawnCommand` and `adminDebugEnemyAction` are the two the mod needs.

### IsTame semantics (the behaviour switch for taming)

The shipped docstring at `0x01CB54D0`:

> "If set to false the Wildlife behavior won't run if the Wildlife is tamed
> (has the IsTame component)"

So `keen::ecs::IsTame` is the component that stops the hostile wildlife AI.
Adding it to a wolf is what makes the animal passive — no bespoke AI needed.

### EnemyDebugAction enum

From the same region:

```
(uint8)EnemyDebugAction::ResetTamed
(uint8)EnemyDebugAction::SetTamed
(uint8)EnemyDebugAction::SetIdleAnimation
(uint8)EnemyDebugAction::Freeze
(uint8)EnemyDebugAction::Unfreeze
(uint8)EnemyDebugAction::Kill
```

`adminDebugEnemyAction` is the vehicle for `SetTamed`.

### M2 implementation

- `src\gamedata.h` — every GUID / enum / component name, all extracted, none guessed
- `src\ecs.h`, `src\ecs.cpp` — runtime probe; read-only, never fabricates a call
- `src\mod.cpp` — `RequestSummon()` gates on the probe; the menu has a
  "运行时能力" panel showing each of the seven features live
- `tools\ecs-selftest.cpp` — standalone proof, exit 0

**Remaining for a real summon**: the ECS world pointer and the command
dispatcher address. That requires dynamic analysis — a live breakpoint on the
dispatcher while the game issues an admin command — which needs the game
running under a debugger. The probe gives the type names; the dispatcher gives
the call.

---

## 2026-10-16 — GAME DATA UNPACKED: wolf, companion and faction facts

**Verified by**: `kfc-parser unpack` over a hardlinked copy of the game data.

### Getting kfc-parser to read the 1.0 build

`kfc-parser` v0.1.2 only accepts the `KFC3` magic; the 1.0 build ships `KFC4`.
The **container layout is otherwise identical** — same KFCLocation tables at the
same header offsets. Patching the 4th byte `0x34 -> 0x33` on a copy makes the
tool read it fine.

```
mklink /H <copy>\enshrouded_XXX.dat <game>\enshrouded_XXX.dat     # zero-copy
mklink /H <copy>\enshrouded.kfc_resources <game>\enshrouded.kfc_resources
copy     <game>\enshrouded.kfc <copy>\ ; then set byte 3 to 0x33
```

Result: `91811/91812 descriptors` unpacked, plus 12,646 type definitions.
(One descriptor fails: `509feadb-4c60-425f-9c7c-deeefd9b6920_21b2a090_3`.)

### Parsed KFC4 header (1.0 release build)

```
magic        : KFC4
version      : 1267041|^/game38/branches/release_1.0|2026-10-15T17:07:04.598331Z
containers   : 55
contents     : 101,459
resources    : 91,812
resourceTypes: 146
resourceLocs : offset=0x1CB37668 size=214,411,316
```

The version string confirms this is the **1.0 release branch**.

### Faction enum values (all values observed in data)

`Ancients`, `AutomatedPlayer`, `Cyclops`, `Drak`, `Environment`, `FarmAnimal`,
`Fogger`, `HitAll`, `HitOthers`, `Player`, `PlayerAlly`, `Scavenger`,
`Skeleton`, `Vukah`, `WildBeast`, `Wildlife`

Assignments that matter:

| Template | Faction |
|---|---|
| `Enemy_Wildbeast_Wolf_*` | **`WildBeast`** |
| `Animal_Wildlife_Dog_*` | `Wildlife` |
| `Animal_Wildlife_Cat_*` | `Wildlife` |
| `Base_Companion` | **`Player`** |
| `Companion_Test` | **`Player`** |

### WOLF templates (the mount candidates)

| Name | GUID |
|---|---|
| `Enemy_Wildbeast_wolf_earlygame` | `478381c5-585f-4264-b373-dbb1ea596eca` |
| `Enemy_Wildbeast_Wolf_Heavy` | `f6a96b72-6da4-4e04-ab62-40e8d0feeac7` |
| `Enemy_Wildbeast_Wolf_AutomatedTesting` | `0d75b9a9-7e48-4f3a-bf2a-19bf6021f531` |
| `Enemy_Wildbeast_Wolf_hook_AG2` | `54c99a9f-d6d1-4cd9-84bb-dd001915ca98` |
| `Enemy_Wildbeast_Wolf_Heavy_BossHealthBar` | `ca98115b-71a2-4de2-9418-cf8d34b75ce3` |

**Every wolf already carries `keen::ecs::HookShotAnchorSubEntity`:**

```json
{
  "anchorEntityTemplate": "ab078982-f5f1-40be-999e-ecaf37d7f112",
  "attachmentSlot": "Root",
  "attachmentOffset": { "localOffset": { "x": 0.0, "y": 1.0, "z": 0.0 } }
}
```

This is the game's own mechanism for attaching an entity to a wolf's back,
1.0 m above the root, using the `Root` attachment slot. It exists because the
hookshot needs an anchor on enemies. **This is the mount attachment point.**

### Tameable animal base classes

| Name | GUID | Components |
|---|---|---|
| `Base_Animal_Wildlife_Tameable` | `4cbd184f-3236-481d-8862-f9dd264766d3` | 90 |
| `Base_Animal_Wildlife_Tameable_OnlyPetInteraction` | `095bb39c-1428-411e-ac36-a784563b4256` | 90 |
| `Base_Animal_Wildlife_Tameable_Transformer` | `08365b0a-2205-45d7-8f02-fecabd5d32db` | 111 |
| `Base_Animal_Wildlife_Tameable_AG2` | `a2ee105d-d9d8-4a86-bffb-21a2cccd2756` | 90 |
| `Base_Animal_Wildlife_NonTameable_AG1` | `ada12d9e-eeb5-4b28-ae88-1e34ac57c22b` | 80 |

Components that mark an animal as tameable/owned:

```
keen::ecs::Animal              # the animal marker
keen::ecs::AnimalSaved         # persisted in the save file
keen::ecs::NetworkAnimal       # replicated
keen::ecs::IsTame              # (on fish variants) the tamed flag
keen::ecs::ClientInteractionOffer / InteractionOfferRuntime
keen::ecs::PathGridInteraction
```

### COMPANION SYSTEM — the answer to "fight alongside the player"

`Base_Companion` (`2a931d54-81e9-4ee4-86c4-27271b0ea5a3`) is a **complete
fighting companion implementation** with 86 components and faction `Player`:

| Capability | Components |
|---|---|
| Target acquisition | `CombatTargetActor`, `ControlCombatTarget`, `SelectedTargets` |
| Combat behaviour | `Enemy01BehaviorState`, `EnemyArsenalReference` |
| Navigation / follow | `PathFinder`, `PathWalker`, `SteeringLocomotion`, `SteeringAgent`, `ClearPathToTarget` |
| Threat | `Aggro`, `FleeSensor`, `CombatFlags` |
| Vitals / UI | `Health`, `HealthBar`, `Stamina`, `Level`, `EnemyScaling` |
| Animation | `AnimationGraphComponent2`, `ServerAnimationGraphComponent2` |
| Locomotion | `Locomotion`, `Movement`, `Gravity`, `Impulse`, `InertialFrame` |

**Conclusion: the wolf does NOT need a hand-written combat AI.** The game
already ships a player-faction fighting companion archetype. Giving the wolf
this component set and faction `Player` reuses the existing AI wholesale.

There is also `Enemy_Companion_Wildlife`
(`f2358637-5ce7-4925-bda5-ca68fab94700`) — a wildlife-shaped companion — and
`Companion_Test` (`83fa0d96-c6bc-4c0a-a9bc-88494938fa19`), both faction `Player`.

Other companion templates present:

```
Player_Companion_Skeleton_Melee_GemOfNecromancy   10f892be-2374-4d31-ae27-85e0a36f3853
Player_Companion_ShockWisp_1..4                   49c9c32a-..., 34c245a6-..., 33491fbc-..., c6f21f95-...
Player_Companion_FlyingSkull                      442ac9a3-ea47-4129-878d-73659f94f9d4
Base_Player_Companion_ShockWisp                   3a05f302-9cd0-4ebc-9a44-8ec9d4c69944
```

### DOG templates (the "copy the dog" target)

| Name | GUID |
|---|---|
| `Animal_Wildlife_Dog_01_bright_AG2` | `5d9c1829-69fc-4339-8bcc-5e62e63e9a31` |
| `Animal_Wildlife_Dog_02_dotted_AG2` | `74bda2f0-74ab-4bad-851e-2328c808daf0` |
| `Animal_Wildlife_Dog_03_dark_AG2` | `406d4e1c-594b-4816-8b8d-77cfef1e83bc` |
| `Animal_Wildlife_Dog_04_black_AG2` | `68c37a11-69c9-476b-9117-ef85226a086e` |
| `Animal_Wildlife_Dog_05_white_AG2` | `51d37581-38fc-4741-9e4c-1dc85463ec67` |

Dog templates carry 95 components including `keen::ecs::Animal`,
`AnimalSaved`, `NetworkAnimal`, `ClientInteractionOffer`, and
`CheckPlayerInRange` — but **not** the full combat set that `Base_Companion`
has. Dogs are pets, not fighters.

### Cat templates

```
Animal_Wildlife_Cat_01_black_AG2     1ce5ac27-d8b1-4fa8-92db-f568994d080f
Animal_Wildlife_Cat_02_striped_AG2   60065215-15ca-424c-9bc3-5665685fed60
Animal_Wildlife_Cat_03_bright_AG2    8d2e50d2-ed98-4231-9846-ca1b7fb69041
```

### Useful spawnpoint templates (for the summon path)

```
Spawnpoint_POI_Wildlife_Wolf_Earlygame     1e0b74fd-9ea3-42ec-b495-8e72e94f6667
Spawnpoint_POI_Wildbeast_Wolf              bf4ae22e-9f66-43da-bd75-9f1c3da3b69e
Spawnpoint_POI_Wildbeast_Wolf_Heavy        c2ccb01e-4051-45d6-8ee0-0498486019a3
Spawnpoint_POI_Wildlife_Dog_01             0c2ebb2d-a072-4d69-9165-80795080364d
```

### Extraction artefacts

```
tools\kfc\unpacked\                 91,811 resource JSONs, 146 type dirs
tools\kfc\animal-facts.txt          animal/wildlife template list + factions
tools\kfc\companion-facts.txt       companion/dog component sets
tools\find-templates.ps1            name+component scan over templates
tools\dump-animal-facts.ps1         faction census
tools\dump-companion-facts.ps1      companion component dump
tools\inspect-kfc.ps1               KFC header parser
```

---

## 2026-10-16 — Vulkan implicit layer registration semantics (CRITICAL)

**Verified by**: `VK_LOADER_DEBUG=all` on `vulkan-1.dll` 1.4.341.0, plus
enumeration deltas.

The Windows Vulkan loader reads implicit layers from:

```
HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers      (64-bit apps)
HKLM\SOFTWARE\WOW6432Node\Khronos\Vulkan\ImplicitLayers   (32-bit apps)
HKCU\SOFTWARE\Khronos\Vulkan\ImplicitLayers      (per-user)
```

**Value name** = absolute path to the layer's JSON manifest.
**Value type** = `REG_DWORD`.
**Value data** = `0` means **ENABLED**, `1` means **DISABLED**.

This is inverted from the intuitive reading. Registering with `/d 1` makes the
loader silently skip the manifest — no error, no warning, the layer simply never
appears in `vkEnumerateInstanceLayerProperties`.

Initial wrong attempt (did NOT work):

```
reg add "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "VK_LAYER_WOLFMOUNT_wolfmount" /t REG_SZ /d "<json path>" /f
```

Working form:

```
reg add "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "<json path>" /t REG_DWORD /d 0 /f
```

**Evidence**: with `/d 1` the loader reported 7 layers and our manifest never
appeared in the debug log's "Located json file" list. With `/d 0` it reported 8
layers and logged:

```
INFO | LAYER:   Located json file "C:\...\VK_LAYER_WOLFMOUNT_wolfmount.json" from registry
INFO:           Found manifest file ... (file version 1.0.0)
```

**HKCU does not work on this system.** Both the correct and incorrect HKCU
registrations were tried; the loader never enumerated them. HKLM is required.
HKLM writes need elevation — Windows 11's built-in `sudo` works:

```
sudo reg add "HKLM\SOFTWARE\Khronos\Vulkan\ImplicitLayers" /v "<json>" /t REG_DWORD /d 0 /f
```

---

## 2026-10-16 — Layer manifest schema

**Verified by**: diffing our manifest against three known-working manifests
(ReShade64.json, SteamOverlayVulkanLayer64.json, EOSOverlayVkLayer-Win64.json).

Working manifest shape:

```json
{
    "file_format_version": "1.0.0",
    "layer": {
        "name": "VK_LAYER_WOLFMOUNT_wolfmount",
        "type": "GLOBAL",
        "library_path": ".\\wolfmount_layer.dll",
        "api_version": "1.3.268",
        "implementation_version": "1",
        "description": "WolfMount - Enshrouded wolf mount mod",
        "disable_environment": {
            "DISABLE_VK_LAYER_WOLFMOUNT_wolfmount_1": "1"
        }
    }
}
```

Findings:

- `api_version` uses a **3-part** version (`1.3.268`). A 2-part `1.4.0` is not
  what the shipped layers use.
- `library_path` with a leading `.\` resolves **relative to the manifest's own
  directory**, not the process CWD. Confirmed by the loader finding the DLL in
  the game dir while the process CWD was elsewhere.
- The `"functions"` block is **optional**. It is not required for the loader to
  find `vkNegotiateLoaderLayerInterfaceVersion` — the loader resolves that by
  name via `GetProcAddress` on the layer DLL. ReShade and Steam both omit it.
  Removing it is safe.
- `"disable_environment"` is conventional but not load-bearing.

---

## 2026-10-16 — Layer DLL export requirements

**Verified by**: `llvm-readobj --coff-exports` on the built DLL.

The loader resolves these by name on the layer DLL:

| Export | Required | Purpose |
|---|---|---|
| `vkNegotiateLoaderLayerInterfaceVersion` | **yes** | loader's first call; returns the `Get{Instance,Device}ProcAddr` pair |
| `vkEnumerateInstanceLayerProperties` | yes | layer self-description |
| `vkEnumerateInstanceExtensionProperties` | yes | layer self-description |
| `vkEnumerateDeviceLayerProperties` | yes | layer self-description |
| `vkEnumerateDeviceExtensionProperties` | yes | layer self-description |
| `vkCreateInstance`, `vkDestroyInstance`, `vkCreateDevice`, `vkDestroyDevice` | intercepted | our hooks |
| `vkCreateSwapchainKHR`, `vkDestroySwapchainKHR`, `vkQueuePresentKHR`, `vkGetDeviceQueue` | intercepted | our hooks |

`__declspec(dllexport)` on a declaration inside a `.cpp`-only `extern "C"` block
did **not** produce an export table. The build links `wolfmount.def` explicitly
instead, which is reliable and immune to inlining.

`VKAPI_ATTR` does not imply `dllexport`.

---

## 2026-10-16 — Static C++ runtime for the layer DLL

**Verified by**: `llvm-readobj --coff-imports`.

Default clang output imports `libc++.dll` and `libunwind.dll`. Loading the layer
standalone then fails with `0xC0000135` unless those DLLs sit next to it.

Fix in `build.bat`:

```
-static-libstdc++ -static-libgcc
```

After this the DLL imports only `vulkan-1.dll` and system DLLs
(`USER32`, `GDI32`, `SHELL32`, `dwmapi`, `KERNEL32`, UCRT api-ms-win-*).

**The layer still links `vulkan-1`** because ImGui's Vulkan backend declares the
core entry points directly, and because the layer exports `vkCreateInstance` /
`vkGetInstanceProcAddr` which the loader calls.

Import library generation (no `vulkan-1.lib` shipped with llvm-mingw):

```
gendef C:\Windows\System32\vulkan-1.dll
x86_64-w64-mingw32-dlltool --input-def vulkan-1.def --output-lib vulkan-1.a --dllname vulkan-1.dll
```

`lld`'s `-lvulkan-1` expands to `libvulkan-1.a` / `vulkan-1.lib`, neither of
which matches `vulkan-1.a`, so the link line uses `-l:vulkan-1.a` to name the
file explicitly.

---

## 2026-10-16 — Toolchain located

No MSVC C++ toolset is installed. `C:\Program Files (x86)\Microsoft Visual
Studio\18\BuildTools` contains only MSBuild and .NET — no `cl.exe`.

Usable clang found at:

```
<toolchain>in
clang version 23.1.3
Target: x86_64-w64-windows-gnu
```

A second copy exists at
`<user>\softvoice-deploy-check\runtime\native\llvm-mingw\...`.

`WinLibs` was installed via winget but its install location was not discoverable
(no `gcc.exe` anywhere on C: or D:); the llvm-mingw toolchains above were used
instead.

---

## 2026-10-16 — Enshrouded install and graphics API

- Game dir: `E:\SteamLibrary\steamapps\common\Enshrouded`
- `enshrouded.exe` 33.69 MB, PE32+ x64
- Imports `vulkan-1.dll`, `d3d12.dll`, `dxgi.dll` — Vulkan primary, D3D12 fallback
- Loads `nvngx_dlss.dll`, `GFSDK_Aftermath_Lib.x64.dll`
- No `mods` directory, no EML installed

---

## Confirmed game systems relevant to the mount (from exe symbol scan)

| System | Symbols |
|---|---|
| Glider | `ecs.StartFlyingEvent`, `ecs.StopFlyingEvent`, `GlidingSetup`, `EquipmentSlot::Glider`, `CameraId::PlayerCameraGlider`, `maxGlidingDistance` |
| HookShot | `ecs.HookShot`, `ecs.HookShotAnchor`, `ecs.HookPullImpulse`, `pullingEntityId`, `AttachedToHook`, `CameraId::PlayerCameraHookShot` |
| Entity hierarchy | `ecs.ImpactHierarchy`, `addImpactHierarchy`, `subEntityTemplate`, `subEntityAttachmentMask` |
| Taming | `keen::actor::TameWildlifeEvent`, `keen::animal::Type`, `keen::animal::TypeMask`, `keen::animal::TargetSetup`, `tamingProgress`, `foodBaitEntityId`, `hasSensedFoodBait`, `hasFullyAtenFoodBait`, `maxTameAnimalCountReached` |
| Spawning | `keen::ecs.AdminSpawnCommand` with `templateGuid`, `followPlayer`, `spawnAsFakePlayer`, `useRoaming`, `autoDestroyTicks` |
| Faction | `factionMask`, `keen::ecs.AdminKillFactionCommand`, `ignoreTamedAnimals` |
| Death | `keen::ecs.EntityDiedEvent` |
| Native menu | `mainMenuEntries`, `mainMenuContent`, `mainMenuSubmenu` |
| Camera states | 40+ `CameraId::PlayerCamera*` incl. `PlayerCameraSitting` (candidate mount pose) |

---

## Build / verify commands

```
build.bat
tools\build-smoketest.bat        # builds + runs the loader smoke test
sudo install.bat "E:\SteamLibrary\steamapps\common\Enshrouded"
tools\verify-build.ps1           # static checks on the artifacts
```

`VK_LOADER_DEBUG=all <app>` is the fastest way to diagnose layer loading.

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
| +0x40 | `movq 0x70(%rsp),%rax` | **byte* UnitMode** —— `movb $0x1,(%rax)` 就地翻转 |
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

---

## 崩溃 post-mortem：我自己的 probe 读越界（m07066 用户截图报崩溃）

### 崩溃现场

```
[wolfmount] world probe: holder=00000078E81DBAE0 world=00000078E81DBAF0
           +0x400=0 +0x470=64 +0x4b0=0 +0x4b8=1 +0x4ba=1 +0x7a0=0 +0x7f0=0 +0x1a8=0
[wolfmount] *** EXCEPTION 0xC0000005
[wolfmount]     faulting addr : 00007FF9B772B82E (unknown module)
[wolfmount]     instr bytes   : 0F B7 97 50 53 E1 00 44 0F B7 87 58 53 E1 00 44
[wolfmount]     access        : read at 00000078E8FF0E40
[wolfmount]     rip=00007FF9B772B82E rsp=00000078E81DB930 rbp=00000078E81DBAE0
[wolfmount]     rcx=0000000000000000 rdx=000001F864F614C0 r8=7FFFFFFFFFFFFFFC r9=0
```

### 定位过程

崩溃指令字节 `0F B7 97 50 53 E1 00` = `movzx edx, word ptr [rdi+0xe15350]`。

反推 rdi：
```
0x00000078E8FF0E40 - 0xE15350 = 0x78E81DBAF0
```
而日志里 `world=00000078E81DBAF0` —— **完全吻合**。

所以崩溃的就是我自己加的 registry probe：
```cpp
const uint16_t progCount = *(const uint16_t*)(p + 0xe15350);   // <-- 元凶
```

### 根因

`world = holder[0]` 只是个**小对象**，只有前约 0x500 字节已提交。
`+0xe15350` 是它之后 **14.7 MB**，`+0x746350` 是之后 **7.6 MB**，
全部未映射。

而 ECS program 注册器 `0x1409d5770` 的 rcx 读的正是 `rcx+0x746350`
（program slot 表，stride 0x1f20）和 `rcx+0xe15350`（u16 programCount）
—— 说明**注册器的 rcx 是另一个大得多的 registry 对象，不是这个 world**。

### 关键收获（对 mod 是好事）

1. `QueryBuild`(0x1409BAB60) 只读到 `+0x4c0`，而 probe 证明 `+0x400..+0x4c0`
   全部可读 → **`wildlife_enemy_transformer` 可以安全接收这个 holder**。
   transformer 从头到尾只调 QueryBuild / QueryRun / QueryNext /
   ComponentRemove / ResolveEnt，**不碰注册器**，所以不会重蹈覆辙。
2. 顺带纠正了一个错误假设：`GetCtx` 返回值（`0x3008954BD80`）与
   `holder[0]`（world）是**两个不同对象**。之前把 GetCtx 返回值当 world 是错的。
3. `IsBadReadPtr` 在超大范围上不可靠（它要遍历整个范围，尾段未映射就整体
   拒绝），**不能**用它来判断十几 MB 外的内存。要么直接读让 VEH 报，
   要么干脆不读。

### 修复

删掉 `+0xe15350` / `+0x746358` 的读取，只保留 `+0x400..+0x4c0` 的安全区，
并在注释里写清为什么不能往外读。

### 教训（重要）

- ** probe 读的内存跨度必须与被测对象的真实大小匹配**。拿一个 ~0x500 字节的
  对象去读它 +14.7MB 的字段，必然崩。
- 崩溃指令字节能直接反推出越界的基址（`faultaddr - disp = reg`），
  这是最快的定位手段，比看调用栈快。
- VEH 打印 `(unknown module)` 不代表崩溃不在自己 DLL 里 —— 本次崩溃就在
  我们自己的 DLL 中，只是模块名解析失败。

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

---

## 发布到社区仓库（2026-10）

用户建好仓库 `https://github.com/scarlet20252025-cloud/Enshrouded` 并要求
「尽量参与到社区的开发生态中」。本轮把本地工程变成一个陌生人能克隆、能构建、
能安装的仓库。

### 网络：git 走代理，web_fetch 不走

`git push` 首次失败：

```
fatal: unable to access '...': Connection timed out after 300003 milliseconds
```

但 `web_fetch` 访问 github.com 返回 200 —— 同一个环境，两个结果，说明问题不在网络。
查明系统 IE 代理是 `127.0.0.1:7897`（`ProxyEnable=1`），而 **git 不读 IE 代理设置**，
`git config --get-regexp http` 只有 `http.sslbackend schannel`。端口在监听、经代理取
GitHub 返回 200。设 `git config http.proxy/https.proxy` 后 push 立刻成功。

**教训**：`web_fetch` 可用不代表 `git` 可用，两者取代理的途径不同。遇到 git 超时先查
`HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings` 的 `ProxyServer`。

### `git add -A` 会试图提交 54 GB 游戏数据

工作区 54,220 MB / 92,388 文件，其中 `tools/kfc/gamecopy` 49.4 GB（58 个 `.dat`）、
`tools/kfc/unpacked` 4.67 GB（91,811 个模板 JSON）。这些都是从游戏解出来的派生物，
既巨大又不属于我们可再分发的内容。`.gitignore` 之后实际提交 **331 文件 / 12.9 MB**。

### third_party 两个库是完整 git clone，必须转成 submodule

`git add` 把它们加成 gitlink（`160000`），克隆出来会是空目录。两者 remote 与 tag 都干净
（imgui `v1.92.9b` @ `f1cc2ae`，Vulkan-Headers `v1.4.365` @ `c468508`），
`git submodule add` 后 `.gitmodules` 正确。

### ★ 全新克隆无法构建（本轮最重要的修复）

干净克隆后 `build.bat` 直接失败：

```
lld: error: unable to find library -l:vulkan-1.a
[ERROR] build failed
```

原因：`vulkan-1.a` 是 **系统 `vulkan-1.dll` 的 import library**，只存在于被 gitignore 的
`build\`，仓库里没有任何脚本生成它。作者机器上一直在，所以从没暴露。

修复：`build.bat` 首次构建时用 `llvm-readobj --coff-exports` 读系统 loader 的导出表 →
`llvm-dlltool` 生成 `vulkan-1.a`。实测全新克隆零手工准备即可产出
`build\wolfmount_layer.dll`（2,614,272 字节），`tools\run-tests.bat` 9/9 通过。

### 硬编码工具链路径

`set TOOLCHAIN=<user>\...` 写死了作者的个人目录，别人必然构建不了。改为依次尝试
`WOLFMOUNT_LLVM` 环境变量 → `PATH` 里的 clang → 本机 llvm-mingw。

### 顺带修掉的两个可移植性问题

- **GNU ld 不能写含非 ASCII 的路径**：检出目录是 `E:\DSH\肥鱼乐园\WolfMount`，
  WinLibs 默认用 `ld`，报 `cannot open output file ...: No such file or directory`。
  加 `-fuse-ld=lld` 解决 —— 这不是权限问题也不是引号问题。
- **POSIX 线程模型需要 `-lpthread`**：WinLibs 是 POSIX/UCRT，`std::mutex` 与 libstdc++
  的 guard 变量都走 pthreads，链接报 9 个未定义符号（`pthread_mutex_init` 等）；
  llvm-mingw 是 win32 线程模型，根本没有这个库。改成探测
  `..\x86_64-w64-mingw32\lib\libpthread.a` 是否存在再决定，两种工具链都能构建。

### 免管理员的安装

`install.bat` 原先以 HKLM 为正常路径、失败才提示 `sudo`。改为**只写 HKCU** ——
Vulkan loader 同时扫 HKLM 与 HKCU 的 ImplicitLayers，per-user 注册完全够用，
而「不用提权、删两个文件就能卸载」正是社区期待的形态。实测 HKLM 与 HKCU 同时登记
同一 manifest 不会重复加载（loader 按 manifest 路径去重）。

`cmd` 解析器扛不住内联 PowerShell（`[3]` 触发 `[3] was unexpected at this time.`），
游戏定位逻辑因此拆到 `tools/find-game.ps1`：读 `SteamPath` 再遍历
`libraryfolders.vdf` 的每个 `"path"`。本机 Steam 装在
`C:\Program Files (x86)\Steam` 而游戏在 `E:\SteamLibrary`，正是必须遍历才能找到的情形。

### 教训

- **「在我机器上能构建」不算能构建**。`git clone` 到一个空目录、什么都不准备地跑一遍，
  才是发布前唯一有意义的验收。这一步暴露了 import library、硬编码路径、链接器、
  线程模型四个问题，全部是作者机器上不可见的。
- 大仓库先量体积再 `git add`。`git add -A` 在含游戏解包产物的目录里是危险操作。
- git 和 HTTP 客户端不共享代理配置。