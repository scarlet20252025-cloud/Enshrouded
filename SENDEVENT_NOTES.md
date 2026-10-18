# SendEvent 语义定论（2026-10-19，权威）

`enshrouded.exe` rva `0x955400` 全反汇编结果：

```
140955400: subq $0x28,%rsp
140955404: movq %rcx,%r11                 ; r11 = buf
140955407: cmpl $0x100,%r8d               ; *** 关键 ***
14095540e: jae  fail                      ; typeTag 必须 < 0x100
140955410: movl %r8d,%r10d
140955413: movl %r8d,%eax
140955416: andl $0x7,%r10d
14095541a: je   0x140955422
14095541c: subl %r10d,%eax
14095541f: addl $0x8,%eax                  ; eax = align8(r8d)
140955422: movl 0x10(%rcx),%ecx           ; ecx = buf->writeIndex
14095542f: cmpq 0x8(%r11),%rax            ; vs buf->capacity
140955433: ja   fail
140955435: movq (%r11),%rax               ; rax = buf->data
140955438: movl %r10d,0x10(%r11)          ; writeIndex += 8 + align8(size)
140955441: movl %edx,(%rcx,%rax)          ; [slot+0] = value      (u32)
140955448: movb %r8b,0x6(%rcx,%rax)       ; [slot+6] = typeTag      (u8)
14095544f: movw %r9w,0x4(%rcx,%rax)       ; [slot+4] = size       (u16)
140955455: movb $0x0,0x7(%rcx,%rax)       ; [slot+7] = 0
140955461: callq memset(rdx=slot+8, len=typeTag)
140955466: leaq 0x8(%rbx),%rax            ; 返回 slot+8
```

## 真实签名

```
void* SendEvent(void* buf, uint32_t value, uint32_t typeTag, size_t size)
```

- `buf` = `{void* data@0; size_t capacity@8; u32 writeIndex@0x10}`
- `value` → `[slot+0]`（唯一的自由负载，4 字节整数）
- `size`  → `[slot+4]` (u16)
- `typeTag` → `[slot+6]` (u8)，**必须 < 0x100**
- payload zeroed，返回 `slot+8`

## 对我们项目的三个直接影响

1. **我们之前的 "HitEvent 过滤" 从未命中过**。`hash == 0xCC0D57E0 && size == 248`
   中 hash 是 u8 上界 0xFF 的参数，永远不可能等于 0xCC0D57E0。此前日志里的
   `HIT #1..9` 不是这条路径产出的。
2. **SendEvent 不是 FNV 哈希事件总线**，是一条「小 tag 整数通道」，无法用它
   提交 SpawnEntityEvent / TameWildlifeEvent。
3. 实机观测（SEND #1..#12）：`buf=00000300895519A8` 固定，`tag=24` size=142
   与 `tag=168` size=570 交替出现 —— 是 UI/输入相关的固定小队列，与游戏逻辑
   事件无关。

## 仍未验证的部分

- `Enqueue`（0x952400）侧只观测到 `keen::ecs::OverrideLevel` 一种组件（400 条），
  payload 为 `E7 7E 1E A2` = 组件哈希本体 + 0x3C 字节 0。
- 这与反射表 `OverrideLevel` 应有字段数不符，说明 **payload 起点或读取时机
  仍有偏差**，不能直接据此断言字段布局。
- 结论：组件读取链路需要重新校准（本次尚无 火把/狼 数据，因为玩家尚未打狼）。
