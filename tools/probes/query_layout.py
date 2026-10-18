r"""Decode the 0xa8-byte query object that wildlife_enemy_transformer passes to
0x1409bab60 (build) and 0x1409b5a50 (consume), by looking at how the handler
reads it back.

Handler reads (rbp = rsp+0x38, so rbp-k == rsp+0x38-k):
  -0x30(%rbp) = rsp+0x08  -> rsi, used as `movzwl 0x40(%rsi)`, `0x30(%rsi)`, `0x18(%rsi)`  = CHUNK/ARRAY header
  -0x38(%rbp) = rsp+0x00  -> rcx, passed as 1st arg to 0x1409c5df0 (component remover)
  -0x40(%rbp) = rsp-0x08 -> u16, stack arg 1 to remover
  -0x3e(%rbp) = rsp-0x0a -> u8,  stack arg 2
  -0x48(%rbp) = rsp-0x10 -> qword, stack arg 3
  -0x50(%rbp) = rsp-0x18 -> qword, stack arg 4
  -0x58(%rbp) = rsp-0x20 -> qword, stack arg 5
  -0x60(%rbp) = rsp-0x28 -> qword, dereferenced and written
  -0x68(%rbp) = rsp-0x30 -> qword
  -0x70(%rbp) = rsp-0x38 -> u16
  -0x6e(%rbp) = rsp-0x3a -> u8
  -0x78(%rbp) = rsp-0x40
  -0x80(%rbp) = rsp-0x48
  0x70(%rsp) -> byte*  (UnitMode byte! `movb $1,(%rax)` at 0x140480f87)
  0x68(%rsp) -> qword
  0x60(%rsp) -> u16
  0x62(%rsp) -> u8
  0x58/0x50/0x48(%rsp) -> qwords

The buffer is at rsp+0x30 (2nd arg = leaq 0x30(%rsp)), 0xa8 bytes.
With rbp = rsp+0x38: buffer start = rbp-0x08. So:
  -0x08(%rbp) = buffer+0x00 .. that's the -0x40/-0x3e pair region? No:
  rsp+0x30 = rbp-0x08. So buffer[i] = rsp+0x30+i = rbp-0x08+i.

  -0x40(%rbp) = rsp-0x08 = buffer+0x38  (u16)
  -0x3e(%rbp) = rsp-0x0a = buffer+0x36  (u8)
  -0x48(%rbp) = rsp-0x10 = buffer+0x28
  -0x50(%rbp) = rsp-0x18 = buffer+0x20
  -0x58(%rbp) = rsp-0x20 = buffer+0x18
  -0x60(%rbp) = rsp-0x28 = buffer+0x10
  -0x68(%rbp) = rsp-0x30 = buffer+0x08
  -0x70(%rbp) = rsp-0x38 = buffer+0x00
  -0x6e(%rbp) = rsp-0x3a = buffer+0x02
  -0x78(%rbp) = rsp-0x40 = OUTSIDE (below buffer)
  -0x80(%rbp) = rsp-0x48 = OUTSIDE

Wait, rsp+0x30 is the buffer, and rbp = rsp+0x38, so buffer = rbp-8.
buffer+0 = rsp+0x30 = rbp-0x08.

So -0x30(%rbp) = rsp+0x08 is NOT in the buffer; it is BELOW rsp+0x30.
Hmm, that contradicts. Let me recompute: rbp = rsp + 0x38 means rbp - 0x30 = rsp + 0x08.
But the buffer starts at rsp+0x30. So -0x30(%rbp) is 0x28 BELOW the buffer.

Actually the prologue: sub rsp,0x108 AFTER lea rbp,[rsp-0x8]. So at the lea, rsp = R.
lea rbp,[R-8]; sub rsp,0x108 -> rsp = R-0x108. rbp = R-8 = rsp+0x100.
So rbp-k = rsp+0x100-k.
  buffer (rsp+0x30) = rbp-0xd0.
  -0x30(%rbp) = rsp+0xd0  -> beyond the 0xa8 buffer end (rsp+0x30..0xd8). That is
  inside the buffer! buffer+0xa0.

So: rbp = rsp + 0x100.
  -0x30(%rbp) = rsp+0xd0 = buffer+0xa0
  -0x38(%rbp) = rsp+0xc8 = buffer+0x98
  -0x40(%rbp) = rsp+0xc0 = buffer+0x90
  -0x3e(%rbp) = rsp+0xc2 = buffer+0x92
  -0x48(%rbp) = rsp+0xb8 = buffer+0x88
  -0x50(%rbp) = rsp+0xb0 = buffer+0x80
  -0x58(%rbp) = rsp+0xa8 = buffer+0x78
  -0x60(%rbp) = rsp+0xa0 = buffer+0x70
  -0x68(%rbp) = rsp+0x98 = buffer+0x68
  -0x70(%rbp) = rsp+0x90 = buffer+0x60
  -0x6e(%rbp) = rsp+0x92 = buffer+0x62
  -0x78(%rbp) = rsp+0x88 = buffer+0x58
  -0x80(%rbp) = rsp+0x80 = buffer+0x50
  0x70(%rsp) = buffer+0x40
  0x68(%rsp) = buffer+0x38
  0x60(%rsp) = buffer+0x30
  0x62(%rsp) = buffer+0x32
  0x58/0x50/0x48(%rsp) = buffer+0x28/0x20/0x18
  0x40(%rsp) = buffer+0x10
  0x30(%rsp) = buffer+0x00

Now decode:
  buffer+0xa0 : qword, read as chunk header {u16 count@0x40, ptr@0x30, u32 cap@0x18}
               -> an ARRAY of entity records (stride 0x800 = shl $0xb)
  buffer+0x98 : qword, 1st arg to 0x1409c5df0 (remove component)
  buffer+0x90 : u16  stack arg
  buffer+0x92 : u8   stack arg
  buffer+0x88..0x50 : qwords (stack args 3..5, and callbacks)
  buffer+0x40 : byte* -> `movb $1,(%rax)` at 0x140480f87  ==> **UnitMode byte**
  buffer+0x10 : qword -> `movb %cl,0x498(%rax)` target (query object)

Conclusion: the 0xa8 buffer is a QUERY DESCRIPTION whose +0x40 points to a
UnitMode byte that gets flipped, +0xa0 is the entity chunk array.
"""
print("rbp = rsp+0x100; buffer = rsp+0x30 = rbp-0xd0; size 0xa8")
print("buffer+0xa0 = entity chunk array {u16 count@+0x40, void* data@+0x30, u32 cap@+0x18}")
print("buffer+0x40 = byte* UnitMode (flipped to 1 = Enemy at 0x140480f87)")
print("buffer+0x98 = 1st arg to remover 0x1409c5df0")
