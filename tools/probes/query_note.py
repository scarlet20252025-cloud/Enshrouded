r"""0x1409bab60 = build query, 0x1409b5a50 = execute query.
- build: rcx = world-ish (reads (%rcx) -> r9, then r9+0x4b0, +0x4b8, +0x4ba,
  r9+0xc0 -> rax, rax+0x400, r9+0x7f0, +0x7a0, +0x1a8). It writes rbx into
  (%rdi) i.e. buffer+0x00 = the world pointer.
- consume: rcx = world-ish, rdx = the SAME buffer. Reads (%rcx)->r8,
  r8+0x830 vs [rcx+8] (a generation/epoch check!) -> returns false if equal.
  Then reads r8+0x4b0, r8+0x470, r8+0x4ba.

KEY: the "query" is just a cached ECS iteration state. buffer+0 = world ptr,
buffer+8 = epoch (u32) that gets stamped so re-runs detect staleness.

For our mod this means: we could build our own 0xa8 buffer with
0x1409bab60(world, &buf, 0xa8), then let 0x1409b5a50 fill the entity array, then
call 0x1409b8010 to advance, and finally 0x1409c5df0 to remove components.

But the whole wildlife_enemy_transformer handler at 0x140480c70 already does all
of this. Its signature is:
   void Transform(void* rcx /* query source / entity */)
with rcx read as: movq (%rcx),%r9 -> r9 is the ECS world.
So rcx must point to an object whose +0 is the ECS world.

The GetCtx hook gave us `store 000000F09C8EB9B0` from world context
000003008954BD80. Let's check: is store+0 == world context? If the object at
world_ctx+0xB8 was the entity id... Actually GetCtx = mov rax,[rcx]; mov rax,[rax+8].
"""
print("Next: check at runtime whether [world_ctx] -> +8 chain matches the store pointer")
