r"""Nail the SendEventEx arg semantics by disassembling the one caller that
tells us what r8d is: func 0x47d5bc at 0x47d751.

    0x47d751  movl 0x88(%rbx), %r8d
    0x47d758  movq %rax, %rcx
    0x47d75b  movl 0x118(%rbp), %edx
    0x47d761  callq 0x140954250       ; SendEventEx(ctx, edx, r8d=?, r9d=0)

and inside SendEventEx:
    0x954250  pushq %rbx
    0x954252  subq $0x30, %rsp
    0x954256  movl %r8d, %ebx          ; keep r8d
    0x954259  movl %edx, %eax          ; keep edx
    0x95425b  testl %r8d, %r8d
    0x95425e  je ret-true              ; if r8d == 0 -> nothing to do
    0x954260  leaq 0x10(%rcx), %rdx    ; rdx = ctx+0x10  (the queue)
    0x954264  movl %eax, 0x20(%rsp)    ; 5th arg (stack) = edx
    0x954268  movl $0x10, %r9d          ; size = 0x10
    0x95426e  movb $0x1, %r8b           ; flags = 1
    0x954271  callq Enqueue             ; Enqueue(ctx, ctx+0x10, 1, 0x10, edx)
    0x954276  testq %rax, %rax
    0x954279  jne ...
    0x954281  movl %ebx, 0xc(%rax)      ; record+0xC = r8d  -> THE TARGET ENTITY ID
    0x954284  return true

So SendEventEx(void* ctx, u32 unusedEdx, u32 entityId, u32 r9d)
"""
import io

TEXT = "SentEventEx signature confirmed: SendEventEx(ctx, edx(ignored), " \
       "entityId, r9d) -> Enqueue(ctx, ctx+0x10, flags=1, size=0x10, edx) " \
       "then record+0xC = entityId"

if __name__ == "__main__":
    print(TEXT)
