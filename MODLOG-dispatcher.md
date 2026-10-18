# 2026-10-18 · dispatcher 搜索记录（未定位，但排除大量死路）

## 已确证的事实

### 1. slot 布局（`func 0x9D48B0`，374 B，逐字节）
```
imul rbx, rax, 0x1F20      ; stride
add  rbx, 0x746350         ; slot array base
add  rbx, rsi
call 0x9A8070             ; lookup
inc  word [rsi+0xE15350]  ; registry count (u16)
mov  [rbx],      r15      ; slot+0x00 = descriptor ptr
movups [rbx+0x10], xmm0   ; slot+0x10..0x1F = descriptor+0x00..0x0F
mov  rax, [r15+0x10]      ; descriptor+0x10
mov  [rbx+0x28], rax      ; ★ slot+0x28 = HANDLER
mov  ecx, [r15+0x180]
mov  [rbx+0x20], ecx      ; slot+0x20 = flags
mov  eax, [r15+0x184]
mov  [rbx+0x24], eax
movzx edx, word [rsi+0xE15350]
mov  [rbx+0x08], dx       ; slot+0x08 = index (u16)
```

### 2. registrar `0x9D4770`（.pdata 未单独列出，实为 `0x9D46E0` 与 `0x9D48B0` 之间的第三个函数）
被 bootstrap `func 0x4A5A30 (17344 B)` 调用 **817 次**，另被 16 个 70 字节小函数
`0x122B1A0..0x122B600` 与 `0x4A5595` 附近调用。结构：
```
0x9D4770  prologue (spill rbx/r14; push rbp/rsi/r12/r14/r15; lea rbp,[rsp+0xC9]; sub rsp,0xA0)
0x9D4788  testb $0x2, 0x180(%rdx)     ; descriptor flags bit 1
0x9D4794  mov %rdx,%r14 ; mov %rcx,%rsi
0x9D47A5  jne +0x2D8 -> 0x9D4A83      ; flags&2 => skip dedupe
0x9D47A9  xor %edi,%edi               ; index = 0
0x9D47AC  cmp 0xE15350(%rcx),%di      ; vs world program count (u16)
0x9D47B3  jae +0x45 -> 0x9D47FA
0x9D47B5  lea %r14,[rcx+0x746360]     ; ★ slot array base
0x9D47BC  movups %xmm0,[%r14]         ; loop: load descriptor+0x00
0x9D47C0  lea %rdx,[rbp-0x49]
0x9D47C4  movups %xmm1,[%r14]
0x9D47C8  lea %rcx,[rbp-0x39]
0x9D47CC  movaps [rbp-0x49],%xmm0
0x9D47D1  movaps [rbp-0x39],%xmm1
0x9D47D8  call 0x895950               ; length-aware buffer compare
0x9D47DD  test %al,%al ; jne +0x55    ; duplicate => bail
0x9D47E3  movzx %eax, word [rsi+0xE15350]
0x9D47EB  inc %rbx
0x9D47EF  add %r14, 0x1F20            ; next slot
0x9D47F6  cmp %rbx,%rax ; jb 0x9D47BC ; loop
```
`0x895950` 是通用 memcmp（先比长度字段 @+8，再 8 字节块 + 1 字节尾）。
→ **registrar 按 descriptor+0x00 的 16 字节 GUID 去重**，写入 `world+0x746360` 起的槽数组。

### 3. `0x1F20` stride 指令全集（20 处，14 个函数）
```
site      func                  字节
0x95B4E5  func 0x95af10 (2549) 4D 69 EC 20 1F 00 00 ...   imul r13, r13, 0x1F20
0x95B58B  func 0x95af10        48 81 C7 20 1F 00 00       add rdi, 0x1F20
0x97FE5F  func 0x97fc10       48 81 C3 20 1F 00 00       add rbx, 0x1F20
0x980403  func 0x9800e6       49 81 C4 20 1F 00 00       add r12, 0x1F20
0x984B32  func 0x984300       49 81 C6 20 1F 00 00       add r14, 0x1F20
0x984C6B  func 0x984300       49 69 C0 20 1F 00 00       imul r8, r8, 0x1F20
0x987CB2  func 0x987ca0 (149) 48 69 C8 20 1F 00 00       imul rcx, rax, 0x1F20
0x99C61C  func 0x99c5e0 (168) 48 69 D0 20 1F 00 00       imul rdx, rdx, 0x1F20
0x99EF90  func 0x99e08a (5145)48 69 E8 20 1F 00 00       imul rbp, rax, 0x1F20
0x9A033E  func 0x9a01d0 (485) 48 69 C8 20 1F 00 00       imul rcx, rax, 0x1F20
0x9A07B8  func 0x9a03b5 (1707)48 69 F8 20 1F 00 00       imul rdi, rax, 0x1F20
0x9A5B43  func 0x9a5aa0 (299) 48 69 C8 20 1F 00 00       imul rcx, rax, 0x1F20
0x9B5BBB  func 0x9b5a50 (759) 48 81 C5 20 1F 00 00       add rbp, 0x1F20
0x9D47EB  func 0x9d46e0 (452) 49 81 C6 20 1F 00 00       add r14, 0x1F20
0x9D4941  func 0x9d48b0 (374) 48 69 D8 20 1F 00 00       imul rbx, rax, 0x1F20
0x9E5455  func 0x9e5342       48 81 C6 20 1F 00 00       add rsi, 0x1F20
0x9F2B5B  func 0x9f2b10       48 81 C3 20 1F 00 00       add rbx, 0x1F20
0xA16AD5  func 0xa16910 (690) 49 81 C1 20 1F 00 00       add r9, 0x1F20
0xA16BF5  func 0xa16bd0 (281) 4D 69 F5 20 1F 00 00       imul r13, r13, 0x1F20
0xA16C8B  func 0xa16bd0       48 81 C7 20 1F 00 00       add rdi, 0x1F20
```

### 4. 关键：`func 0x99E08A` 的 0x99EF90 站点读的是 `0x745A28`，不是 `0x746350`
```
0x99EF90  48 69 E8 20 1F 00 00   imul rbp, rax, 0x1F20
0x99EF97  48 81 C5 28 5A 74 00   add  rbp, 0x745A28
0x99EF9E  49 03 ED               add  rbp, r13
0x99EFA1  85 C9                  test ecx, ecx
0x99EFA3  74 29                  je   0x99EFCE
0x99EFA5  83 E9 01               sub  ecx, 1
0x99EFA8  74 0F                  je   0x99EFB9
0x99EFAA  83 F9 01               cmp  ecx, 1
0x99EFAD  0F 85 25 01 00 00      jne  0x99F0D8
0x99EFB3  0F B6 45 20            movzx eax, byte [rbp+0x20]   ; slot flags
0x99EFB7  EB 1B                  jmp  0x99EFD4
```
`[rbp+0x20]` 与 registrar 写的 `slot+0x20 = descriptor flags` 完全对上
→ **`0x745A28 + index*0x1F20` 是 program slot 的另一个基址**（早前记录的
`0x745A48` / `0x745A58` 与之相差 0x20 / 0x30，是同一数组的相邻字段）。

### 5. `func 0x9A03B5` 的 0x9A07B8 站点直接调用了 0x9B5030
```
0x9A07B8  48 69 F8 20 1F 00 00   imul rdi, rax, 0x1F20
0x9A07BF  48 03 3E               add  rdi, [rsi]
0x9A07C2  0F B7 97 10 3B 74 00   movzx edx, word [rdi+0x743B10]
0x9A07C9  E8 62 48 01 00         call 0x9B5030
```
`0x9B5030` 有 4 个调用者：`0x959710` (511 B) / `0x9A03B5` (1707 B) / `0x9E02E0` (1187 B)。

## 排除的死路（勿再重复）

1. **`call [reg+0x28]` 的 modrm 是 0x50..0x77**，早前只列 13 个编码得出「3 sites / 2 functions」是假象。正确范围给出 **42 sites / 40 functions**。
2. **`find_callers.py` 必须用槽内偏移 `i`**，不能加 `traw`；E8 rel32 的 dest = `i+5+rel` 再与 rva 比。加 `traw` 会全 0 命中。
3. **llvm-objdump 是线性扫掠**，mid-instruction 起始地址会让后面全部错位。之前多次「看不懂的汇编」都是这个原因。**字节级读文件才是权威**，`tools/decode_window.py` 用模式匹配绕过。
4. **`0x12CF630` 不是 lea-rip thunk**：该处实际字节是 `8B 74 24 38 48 8B 7C 24 40 ...`（函数体）。早前 TECHNIQUE.md 的「thunk 表 0x12CF5C0 起 stride 0x10」记录**有误，待核**。
5. **14 个候选函数全部 0 个 E8/E9 调用者、0 个 `lea rip-relative` 引用、0 个 8 字节 VA 指针**（全文件扫描）→ 它们只能通过**运行时计算出的函数指针**被调用，即从某个表里 `base + index` 取址。这与「descriptor handler 被复制进 slot」一致，但说明 dispatcher 不在这些函数里。

## 下一步（最有希望的一条）
`0x745A28` 是 program slot 的真实基址（ registrar 写 `0x746360`，walker 读 `0x745A28`，
两者相差 0x838，需查 `world+0x745A28` 与 `world+0x746360` 是否同一结构的不同视图）。
应当：
1. 全文件搜 `0x745A28` 的 4 字节引用，找出所有用户；
2. 在 `func 0x99E08A` (5145 B) 里找「读 slot+0x28 并 call」的字节模式
   （`48 8B 6D 28` / `48 8B 45 28` / `FF 55 28` 之类），这个函数同时具备 stride 与 base，
   是最像 dispatcher 的候选。

## 追加：最终定论（本轮结束）

### func 0x9B5A50 = QueryRun（759 B）不是 dispatcher
0x9B5C28 处 `mov rax,[r14+0x28]` 之后是 `movups [rax+rcx*1],xmm0` 系列写回，
即 **r14+0x28 是输出缓冲区指针**，不是 handler。且 0x9B5BBB 之前 r14 已被
重新赋值，所以它根本不是 slot 指针。QueryRun 遍历 program 槽位
（`add rbp,0x1F20`，count `word[world+0xE14A28]`）只做位图查询与组件写回。

### func 0x9B5030（0xA0 B）是 ECS job 原子状态机
```
0x9B5030  48 83 EC 28              subq $0x28,%rsp
0x9B5034  44 0F B7 D2              movzwl %dx,%r10d
0x9B5038  4C 8B C9                 movq %rcx,%r9
0x9B503B  45 8D 42 FF              leal -0x1(%r10),%r8d
0x9B503F  4D 8D 80 E8 73 1D 00     leaq 0x1D73E8(%r8),%r8
0x9B5046  42 8B 14 C1              movl (%rcx,%r8,4),%edx
0x9B504E  83 FA 02                 cmpl $0x2,%edx
0x9B5051  74 67                    je   0x9B50BA
0x9B505A  F0 41 0F B1 08           lock cmpxchgl %ecx,(%r8)   ; CAS
0x9B5061  F0 41 FF 81 C0 BF EB 00  lock incq 0xEBBC0(%r9)
0x9B507A  F0 46 0F B1 94 0A 40 BD EB 00  lock cmpxchgl %ecx,0xEBD40(%rdx,%r9)
0x9B5095  41 C7 00 02 00 00 00     movl $0x2,(%r8)          ; state = 2
```
与 program handler 无关。

### func 0xA15910 / 0xA16910 = 组件寻址通用 helper（与 M182 layout() 一致）
```
0xA159A7  44 0F B7 46 10           movzwl 0x10(%rsi),%r8d   ; slot index
0xA159AC  4D 8B 4D 18              movq 0x18(%r13),%r9      ; def
0xA159B3  48 C1 E8 06              shrq $0x6,%rax
0xA159BB  49 8B 14 C1              movq (%r9,%rax,8),%rdx   ; 640-bit bitmap
0xA159BF  48 D3 EA                 shrq %cl,%rdx
0xA159C2  F6 C2 01                 testb $0x1,%dl
0xA159CB  41 8B 45 30              movl 0x30(%r13),%eax     ; slot index
0xA159CF  43 0F B7 94 41 84 0A 00 00  movzwl 0xa84(%r9,%r8,2),%edx  ; stride
0xA159D8  48 0F AF D0              imulq %rax,%rdx
0xA159DC  43 0F B7 84 41 84 00 00 00  movzwl 0x84(%r9,%r8,2),%eax   ; offset
0xA159E5  48 03 D0                 addq %rax,%rdx
0xA159E8  49 03 55 20              addq 0x20(%r13),%rdx     ; chunk
0xA159EC  48 89 54 24 40           movq %rdx,0x40(%rsp)
```
`addr = chunk + offset[i] + stride[i]*i`，与 M182 `layout()` 逐字段一致。

### 穷尽性证明：handler 调用点不存在于已知形式
- `FF /2` 间接调用全文件共 **23938 处**，其中 disp==0x28 的 **123 处**（分布在 147 个函数）。
- 含 `imul/alu 0x1F20` 的函数共 **17 个**。
- **两者交集 = 0**。
- 在 17 个 stride 函数里搜 `mov reg,[reg+0x28]`，只有 2 个命中：
  `func 0x9800E6`(1171 B) @0x98055D、`func 0x9B5A50`(QueryRun) @0x9B5AE8/0x9B5C2A。
  后者的 r14 已被重新赋值，不是 slot。

### 结论
`slot+0x28` 上的 descriptor handler **不是**通过 `call [slot+0x28]` 被调用的。
可能形式：handler 被复制到别处后再调、或 dispatcher 用完全不同的槽位布局、
或 16 个 program 根本不由统一 dispatcher 驱动（各自在专门代码里内联）。
**继续搜索的边际收益已低于转向实机验证。**
