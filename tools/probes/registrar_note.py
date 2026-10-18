r"""Summarise what 0x1404a5a30 is: a static bootstrap that registers ~800
behaviour handlers. Print its call-graph summary: it calls 0x1409d5770 ~800
times with different descriptor thunks; 0x1409d5770 is the registrar.

The key insight for the mod: 0x1409d5770(rcx=?, rdx=descriptor_ptr, r8=bool)
registers a behaviour. Signature candidate:

  1404a76bf  callq thunk0x12cf620        -> rax = &descriptor 'wildlife'
  1404a76c4  movq %rax,%rdx              ; rdx = descriptor
  1404a76c7  xorl %r8d,%r8d              ; r8 = 0
  1404a76ca  movq %rbx,%rcx              ; rcx = rbx (registry/world-ish)
  1404a76cd  callq 0x1409d5770

So: void Register(void* rbx, void* descriptor, bool r8). And 0x1409d5770 tests
`testb $0x2, 0x180(%rdx)` — a flag at descriptor+0x180?? No: rdx is the
descriptor... wait 0x9d5770's rdx at entry is the SECOND argument. In the
registration call rdx = descriptor (0x141e2b680 for 'wildlife'), and the
descriptor struct is only ~0xF0 bytes, so descriptor+0x180 would be out of
bounds. Therefore rdx is NOT the descriptor; it is a different object.

Look again: 0x1409d5770 reads 0x180(%rdx) bit 1. Let's disassemble more of
0x1409d5770 and figure out what rdx/rcx are. Also check what rbx is at
0x1404a5a30.
"""
print("see MODLOG")
