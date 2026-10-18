# Working with Enshrouded's ECS without byte signatures

This document is the reusable part of WolfMount. It describes how to find your
way around Enshrouded 1.0's entity system **using the game's own reflection
data**, so that your offsets survive a game update instead of breaking with it.

Everything here was established against the shipped `enshrouded.exe` (Steam
appid 1203620, version 1.0) and re-verified with the tools in `tools\`. Where a
claim is unverified it says so.

---

## 1. Why not AOB signatures

An AOB signature is a byte pattern taken from compiled code:

```
48 8B 05 ?? ?? ?? ?? 48 85 C0 74 ?? ...
```

It works until the function is recompiled and the registers get allocated
differently, which for this game means every patch. Every mod in this community
currently carries a table of signatures annotated with the game build they were
taken from, and the first thing every user does after an update is report that
the table no longer matches.

There is a better substrate. The game ships a **self-describing type system**
for its own ECS, because it needs one at runtime for serialisation and network
replication. That table is *data*, not code. It gives you:

- every component and event type, by fully qualified name
- its size and alignment
- every field's name, offset and type
- a stable 32-bit hash of its name, which is what the game itself passes around

None of that changes when the compiler reallocates registers.

---

## 2. Finding the reflection table

### The table

There is a descriptor (not the array itself) at file offset `0x1717490`:

```
0x1717490:  u64  table_ptr = 0x1416FD950     (a VA)
0x1717498:  u64  count     = 12646
```

`0x1416FD950` is a VA, and `IMAGE_BASE` is `0x140000000`, so:

```
RVA        = 0x16FD950
file offset = 0x16FC350     (via the .rdata section header)
```

At that file offset is an array of **12646 u64 pointers**, each pointing at a
0x90-byte `TypeMetadata` record.

Each `TypeMetadata` record — this layout is authoritative and was verified
against indices 0, 208 and 3298:

| offset | type | meaning |
|---|---|---|
| `+0x00` | `u64` | pointer to the *unqualified* name (`BlobString`) |
| `+0x08` | `u64` | its length |
| `+0x10` | `u64` | pointer to the impact-library name |
| `+0x18` | `u64` | its length |
| `+0x20` | `u64` | **pointer to the qualified name** (`keen::ecs::HitEvent`) |
| `+0x28` | `u64` | its length |
| `+0x30` | `u64` | pointer to the namespace (`keen::ecs`) |
| `+0x38` | `u64` | pointer to the inner/parent type |
| `+0x40` | `u32` | **size in bytes** |
| `+0x44` | `u16` | alignment |
| `+0x46` | `u16` | element alignment |
| `+0x48` | `u32` | **field count** |
| `+0x4C` | `u8` | primitive type (`0x12` = STRUCT, `0x19` = BLOB) |
| `+0x4D` | `u8` | flags |
| `+0x50` | `u32` | **the qualified-name hash** |
| `+0x54` | `u32` | a second, internal hash |
| `+0x58` | `u64` | pointer to the struct-field array |
| `+0x60` | `u64` | pointer to the enum-field array |
| `+0x68` | `u64` | pointer to the variant type |
| `+0x70` | `u64` | pointer to the default value |
| `+0x78` | `u64` | its length |
| `+0x80` | `u64` | pointer to attributes |
| `+0x88` | `u64` | attribute count |

Note there are two bytes of padding at `+0x4E`, so the hash is at `0x50` and not
at `0x4E`. Getting that wrong yields a hash that looks almost right.

Struct fields are `0x30` bytes each:

| offset | type | meaning |
|---|---|---|
| `+0x00` | `u64` | field name pointer |
| `+0x08` | `u64` | name length |
| `+0x10` | `u64` | type pointer (a VA into this same table) |
| `+0x18` | `u64` | **byte offset within the struct** |
| `+0x20` | `u64` | attributes pointer |
| `+0x28` | `u64` | attribute count |

### Locating it reliably

Do not hunt for the array by scanning for a plausible count — you will find the
descriptor's count field and mistake it for the array.

Anchor on the array's **first two entries** instead. Entry 0 is
`keen::BlobString` and entry 1 is `keen::uint32`; those two type records sit at
fixed VAs, so the first 16 bytes of the array are a known constant:

```
0x141AB0530   -> keen::BlobString   record
0x141AB47B0   -> keen::uint32       record
```

The array is preceded by 8 zero bytes of padding, so build a **17-byte** needle:

```
00 <LE64 0x141AB0530> <LE64 0x141AB47B0>
```

The hit offset **+1** is the start of the type array.

Verified end to end: `find(needle) = 0x16FC34F`, so the array starts at
`0x16FC350`; the qword there is `0x141AB0530`, whose record's qualified name is
`keen::BlobString`; and `0x16FC358` is `0x141AB47B0`, whose name is
`keen::uint32`. Entry 2 is `keen::HashKey32`.

Two traps here, both of which produce a near-miss that looks plausible:
- **The pointers are 64-bit.** A 32-bit version of the needle matches nothing.
- **The two pointers point at type records, not at strings.** If you expect them
  to be `char*` and read the bytes at that address as text, you get binary.

---

## 3. The hash is FNV-1a-32 of the qualified name

This is the single most useful fact in this document, because it means you can
compute the hash for a name you only know from a log line or a community post.

```python
def fnv1a32(s):
    h = 0x811C9DC5
    for b in s.encode():
        h = ((h ^ b) * 0x01000193) & 0xFFFFFFFF
    return h
```

Verified against the table:

| name | hash |
|---|---|
| `keen::ecs::Faction` | `0xA1F30F21` |
| `keen::ecs::HitEvent` | `0xCC0D57E0` |
| `keen::ecs::CurrentTransform` | `0x027AC564` |
| `keen::ecs::AdminSpawnCommand` | `0x06DBFCA2` |
| `keen::actor::TameWildlifeEvent` | `0x537B675C` |

Note the two namespaces: components and some events are `keen::ecs::`, actor
events are `keen::actor::`. `TameWildlifeEvent` is the second kind, so hashing it
as `keen::ecs::TameWildlifeEvent` gives the wrong number. This is a common way
to conclude "the event does not exist".

---

## 4. Finding your way from the reflection table to live memory

The table tells you *what* components exist and *what shape* they are. It does
not tell you *where* a given entity's component is. For that you need three
runtime facts.

### 4.1 The world context arrives through `GetCtx`

```
rva 0x9B0860, 396 call sites

1409B0860: 48 8B 01        mov rax,[rcx]      ; store
1409B0863: 48 8B 40 08     mov rax,[rax+8]    ; world
1409B0867: C3              ret
```

This is eight bytes long and every part of the game that needs the world goes
through it. Hooking it means you never have to find a static world pointer:
whatever the game is about to use, you get to see.

**Because it is only 8 bytes you cannot install a 14-byte `FF 25` absolute jump
over it.** Use a 5-byte `E9 rel32`, and put the relay in memory within ±2 GB —
a 64-bit absolute jump needs a `FF 25 00000000 <imm64>` relay stub somewhere the
relative jump can reach. This mod allocates that relay with
`VirtualAlloc2`-style placement near the target (`AllocateNear` in
`src\detour.cpp`).

**Trap**: `GetCtx` returns the world, but `store[0]` is a *different object* that
also satisfies "`[0]` is the world". Early versions of this mod treated the
return value as the world and spent a day on nonsense reads. They are not the
same pointer. `store` is what you pass to functions that want a "holder"; the
return value is what you pass to functions that want a "world".

### 4.2 The entity manager lives behind the world

The manager holds an open-addressed hash map at `manager + 0x148`. The header is
0x58 bytes:

```
manager + 0x148
    +0x08  u64*  bitmap     occupancy bits, one per bucket
    +0x10  u64   capacity   power of two
    +0x28  u32*  keys       bucket -> entity id
    +0x40  u64*  values     bucket -> entity record
    +0x54  u32   count
```

The entity record (0x38 bytes read):

```
    +0x10  u32   entity id   echo, so a stale record can be rejected
    +0x18  void* def         the definition holding the slot tables
    +0x20  void* chunk       the component storage base
    +0x30  u32   slot        which instance inside the chunk
```

The bucket hash is **the engine's own**, not any standard hash:

```c
uint32_t bucket_of(uint32_t id, uint64_t capacity) {
    uint32_t a = ((id >> 16) ^ id) * 0x045D9F3B;
    uint32_t b = ((a >> 16) ^ a) * 0x045D9F3B;
    return (uint32_t)((((uint64_t)b >> 16) ^ b) & (capacity - 1));
}
```

A different constant and every lookup silently misses — it returns "entity not
found" rather than an error, which reads exactly like a dead entity.

Verified live: `count=1301 capacity=1048576` in a loaded world.

**Validate the header before trusting the pointer**: capacity must be a power of
two, under `1 << 26`, and count non-zero. That shape is the only thing separating
an entity manager from an arbitrary object that happens to be at a plausible
address.

**There are two managers.** Only the authority side owns the bytes an AI reads;
a write to the local copy is invisible. The flag is one byte at `manager + 8`
(`0` = server). This mod logged `server=1` when it resolved the manager, which is
the value that matters.

The manager is *also* reachable as a candidate object that satisfies
`[candidate]` being a valid pointer with `>= 0x10000`. That is the constraint the
entity factory imposes (`14097B7b8: movq (%rcx),%rsi` — the first thing it does
is read the world out of its manager argument). **Validate with that constraint
before calling anything**, because an entity factory called with the wrong
manager writes faction bytes into unrelated memory.

### 4.3 Component slots are one global index

A component is addressed by *slot index* into a per-entity definition, not by
hash, at runtime. The slot index is global across every entity definition, so
you find it once.

```
entity definition
    +0x00   640-bit occupancy bitmap   (80 bytes)
    +0x84   u16 offset table           (640 entries)
    +0xa84  u16 stride table           (640 entries)

slot address = chunk + offset[slot] + stride[slot] * slotInChunk
```

This is why "the hash never appears as a read reference" is not evidence that
nothing reads the component — by the time anything reads it, the hash has long
since been resolved to an index. **Do not conclude "no consumer" from "no
literal".** That reasoning error is recorded in `MODLOG.md` because it cost real
time.

---

## 5. Which write path to use

There are three, and using the wrong one fails *silently*.

### The Enqueue path

```
rva 0x952400
void* Enqueue(void* ctx, void* buf, u8 flags, u32 size, u32 entityId)
```

`entityId` is the fifth argument and arrives on the stack. The record it builds:

```
+0x00 u16 size      +0x02 u8 flags      +0x03 0
+0x04 u16 ctx+0x28  +0x06 u16 ctx+0x2A
+0x08 u32 entityId
+0x0C ... payload (zero-filled to `size`)
```

The queue object passed as `buf` is `{data@0, capacity@8, writeIndex@0x10,
count@0x14}`, 16-byte aligned writes.

**This path only works for the component types that actually have an Enqueue call
site.** Many do not. `tools\classify_component.py` answers which, for any type:

```
python tools\classify_component.py "keen::ecs::Faction" "keen::ecs::IsTame"
```

```
keen::ecs::Faction        0xA1F30F21  ARRAY24@14021C3AA OTHER@140222863 ...
keen::ecs::IsTame         0x1399E0BA  OTHER@14047D072 ENQUEUE@14048114B
```

`ENQUEUE` means the descriptor is routed through `0x952400`. `ARRAY24` and
`OTHER` mean it is not — the hash is being stored into some other prebuilt
buffer, and writing through `Enqueue` will do nothing.

Getting this wrong is the classic failure: `Enqueue` returns a valid pointer, you
write your payload, the game proceeds, and the component never changes.

### The 24-byte descriptor / array path

```
rva 0x140953800  packs an array of {u32 hash; void* ptr; u64 size} descriptors
                 into ONE Enqueue record (it calls 0x952400 at 0x1409538AC)
```

`Faction` goes this way. There is a 48-byte setter at `0x14021C390`:

```
14021C390: test r8,r8 ; je ret
14021C395: push rbx ; sub rsp,0x20
14021C39A: movzbl (%r8),%eax        ; the faction value comes from r8
14021C39E: mov rbx,rdx
14021C3A1: movb %al,(%rdx)          ; and is written to the caller's scratch
14021C3A3: call 0x1402202C0         ; 24-byte slot appender
14021C3A8: movl $0xA1F30F21,(%rax)  ; hash
14021C3AE: movq %rbx,0x8(%rax)      ; ptr
14021C3B2: movq $0x1,0x10(%rax)     ; size
```

It **only builds a descriptor**; it does not write the component. And this
function has **zero call sites** in the whole binary — the game does not use it,
it is an inlined helper left behind. So calling it accomplishes nothing at all.

### The honest path: write the byte

`Faction` is one byte in a component slot. The AI reads that slot. So write it:

```c
slot = DiscoverFactionSlot();          // by VALUES, see below
addr = ComponentAddress(entity, slot);
*addr = 11;                            // PlayerAlly
assert(*addr == 11);                   // read back, or it did not happen
```

### Discovering the `Faction` slot without knowing its index

Faction is one byte, its value is a 16-value enum, and in any populated world
both `6` (WildBeast — a wolf) and `7` (Player) are present. No other one-byte
component satisfies all of: width 1, present on live entities, all sampled
values in `[0,15]`, and *both* 6 and 7 observed. The 6/7 pair is what makes it
unambiguous.

This is in `DiscoverFactionSlot()` in `src\entityops.cpp`, and it works because
of a property worth remembering: **you can identify a component by its value
distribution instead of by its name.**

---

## 6. Sending events

`SendEvent` is **not** a general event bus and it is not keyed by FNV hash.

```
rva 0x955400

140955400: subq $0x28,%rsp
140955404: movq %rcx,%r11
140955407: cmpl $0x100,%r8d       ; typeTag MUST be < 0x100
14095540E: jae fail               ; otherwise return NULL
140955422: movl 0x10(%rcx),%ecx   ; buf->writeIndex
...
140955441: movl %edx,(%rcx,%rax)  ; slot+0 = value (u32, the only free payload)
140955448: movb %r8b,0x6(...)     ; slot+6 = typeTag (u8)
14095544F: movw %r9w,0x4(...)     ; slot+4 = size (u16)
140955461: callq memset-like (0x1413ABA00)   ; zero from slot+8
140955466: leaq 0x8(%rbx),%rax    ; returns slot+8
```

Read that carefully: the write index advances by `8 + align8(size)`, the record
header is 8 bytes (`value` u32 at +0, `size` u16 at +4, `typeTag` u8 at +6, a
spare u8 at +7), and **the only caller-supplied data that survives is the single
u32 `value`.** Everything from `slot+8` is cleared.

So the real signature is:

```
void* SendEvent(void* buf, u32 value, u32 typeTag /* < 0x100 */, size_t size)
```

It carries **one 32-bit value**. It cannot carry a 248-byte `HitEvent`. If you
are writing a 248-byte structure through it and then reading it back, you are
reading a zeroed buffer and any values you find there are leftovers from whatever
was in that memory before.

`HitEvent` and the other large events go through a different, batched path:
a caller-side collector array of `{u32 hash; void* ptr; u64 size}` triples,
submitted in bulk. That is the same 24-byte descriptor shape as §5.

---

## 7. Things that look like the answer and are not

Recorded because each one cost real time:

- **126 message-registration thunks.** A tidy set of
  `C7 01 <imm32>` / `48 89 51 08` / `48 C7 41 10 <imm32>` / `C3` sequences —
  i.e. `*(u32*)rcx = hash; *(void**)(rcx+8) = rdx; *(u64*)(rcx+0x10) = size;
  return` — one per reflected type, matching the reflection table exactly
  (126 sites, all 126 hashes found in the table, zero unknown). Find them with
  `tools\scan_msgreg.py`.

  **These look like the answer to "where is the world?" and are not.** They
  build a `{hash, ptr, size}` descriptor, which is the same 24-byte shape the
  real submit path uses. It is tempting to assume they must be called from
  somewhere you can walk back from.

  **They have zero direct `call` references and zero 8-byte VA pointers anywhere
  in the file.** Whatever invokes them, it does it in a way this scan does not
  see — a computed dispatch, or simply not at all on the paths that matter. Treat
  them as self-description and do not build a world-pointer hunt on them. We
  spent time on exactly that.

- **The program descriptor table** (16 entries; 16-byte thunks starting at `.text`
  rva `0x12CF5C0`, each `48 8D 05 <rel32> C3` = `lea rax,[rip+d]; ret`). This
  describes ECS *programs*, including `wildlife_enemy_transformer` — the game's
  own "turn an enemy into wildlife" behaviour — at thunk rva `0x12CF630`
  → descriptor rva `0x1E2B860`, handler rva `0x480C70`.

  These thunks **are** reachable, and the route matters if you want to trigger a
  program. The bootstrap `rva 0x4A5A30` (17344 bytes) calls a thunk to get a
  descriptor and immediately hands it to the registrar:

  ```
  1404a7744: callq 0x1412CF630      ; thunk -> descriptor for wildlife_enemy_transformer
  1404a7749: movq  %rax,%rdx        ; arg2 = descriptor
  1404a774c: xorl  %r8d,%r8d        ; arg3 = false
  1404a774f: movq  %rbx,%rcx        ; arg1 = world
  1404a7752: callq 0x1409D5770      ; Register(world, descriptor, false)
  ```

  The registrar:
  ```
  1409D5770: void Register(void* world /*rcx*/, void* descriptor /*rdx*/, bool /*r8b*/)
  1409D578E: testb $0x2, 0x180(%rdx)   ; descriptor flags bit 1
  1409D57A9: cmpw  $0xe15350(%rcx),%di ; world's program count
  1409D57B2: leaq  $0x746360(%rcx),%r14; the slot array (stride 0x1F20)
  ```

  So the game registers all 16 programs at world bootstrap, including the
  transformer. That is why calling the handler yourself crashes but the game's own
  dispatch of it would not — the program *is* installed, it just is not yours to
  invoke out of band. To use it, hook the dispatcher that walks
  `world+0x746360` (stride `0x1F20`) and calls `slot+0x28`.

- **Calling a program handler directly.** Calling
  `wildlife_enemy_transformer` (`rva 0x480C70`) yourself **crashes the game**:
  `QueryBuild` and `QueryRun` succeed, then it faults at `rva 0x9B8013`
  (`movq 0x58(%rax),%rcx`) dereferencing a garbage pointer. The handler builds a
  0xA8-byte query object on its own stack containing correlation pointers that
  are only valid when the game's own program dispatcher drives it. If you need
  this behaviour, hook the dispatcher; do not call the handler.

- **`KERNEL32.DLL+0x12A96` access violations in the log.** These are the game's
  own probes (`instr bytes 0F B6 01 ...`, `rbp = 0x00C04CEE` which is a `.rdata`
  size constant). They are not crashes. Do not spend a day on them like we did.

---

## 8. Practical notes

### Installing a Vulkan implicit layer

```
key:  HKCU\SOFTWARE\Khronos\Vulkan\ImplicitLayers   (HKLM also works, needs admin)
name: full path to your VK_LAYER_*.json manifest
type: REG_DWORD
data: 0 = ENABLED, 1 = DISABLED        <-- backwards from intuition
```

The loader deduplicates by manifest path, so a stale HKLM entry plus a fresh HKCU
entry does **not** load your layer twice. Verify with `VK_LOADER_DEBUG=layer`
if in doubt.

A `GLOBAL` layer is the right type for an overlay: it gets every instance and
device without the app opting in. `api_version` should not exceed what the game
requests; `1.3.268` is verified working here.

### Logging from inside a game hook

Hot paths run millions of times per world load. Writing a line per call to a
game-thread `fprintf` will stall the present loop badly enough that the player
sees a hung load — we shipped that bug once. Sample: log the first 200, then one
line every 200, and keep exact counts in memory. Never write an uncounted
`hexdump` from a hook.

### Keys

`GetAsyncKeyState` reads global hardware state, so it works even though this game
does not forward `WM_KEYDOWN` to its window procedure — but it also fires when
your window is **not** focused. If a user says "the hotkey stopped working",
check window focus before you check your code.

---

## 9. Tools in this repo

| tool | purpose |
|---|---|
| `tools\peek.py` | PE sections/search/hex/strings/disasm/reflection, the base primitive |
| `tools\scanrefs.py` | every `.text` reference to a type hash, with the containing function from `.pdata` |
| `tools\dump_type.py` | dump any reflection type and its fields, by name or index |
| `tools\tpl_guid.py` | template name → the 16-byte GUID the entity factory takes |
| `tools\classify_component.py` | which write path a given component actually uses |
| `tools\find_wildlife_templates.py` | which templates carry `Animal`/`Wildlife` |
| `tools\diff_templates.py` | component-set diff between two templates |
| `tools\wdisasm.py` | small x86-64 disassembler wrapper |

Do not name a script in `tools\` after a standard-library module. A file called
`dis.py` shadowed Python's `dis` and broke every other script in the folder with
a confusing `AttributeError`. Ask us how we know.

---

## 10. If you find something here that is wrong

Please say so. `MODLOG.md` contains several entries that record this project
being confidently incorrect, including a hand-copied PE section table that was
wrong for a day and invalidated a dozen downstream conclusions. Being wrong in
public with the evidence attached is the point.
