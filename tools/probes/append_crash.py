# -*- coding: utf-8 -*-
"""Append the crash post-mortem to MODLOG.md."""
import io

LOG = r"E:\DSH\肥鱼乐园\WolfMount\MODLOG.md"

TEXT = """
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
"""


def main():
    with io.open(LOG, "a", encoding="utf-8") as fh:
        fh.write(TEXT)
    print("appended %d chars" % len(TEXT))


if __name__ == "__main__":
    main()
