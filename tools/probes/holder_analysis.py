r"""The probe settled a crucial question:

  holder (store)      = 0x000000815A0DBA30
  world  = holder[0]  = 0x000000815A0DBA40   (holder + 0x10)
  ADOPTED ctx         = 0x000003008954BD80   (a DIFFERENT object entirely)

So `GetCtx`'s return value is NOT the object QueryBuild dereferences.
The `store` IS the right holder: QueryBuild reads `*(void**)rcx` and then
`r9+0x4b0`, and our probe confirms world+0x4b0=0, +0x4b8=1, +0x4ba=1,
+0x470=64 — small plausible component counts.

But wait: is `world` really the ECS world? `Enqueue`'s ctx is 0x3008954BD80,
and Enqueue is the component writer that SetIsTame uses. Two different
objects. Which one does QueryBuild want?

QueryBuild reads r9+0x4b0 (u8), r9+0x4b8 (u16), r9+0x4ba (u16), r9+0x400,
r9+0x470, r9+0x7a0, r9+0x7f0, r9+0x1a8. Our probe on `world` gave:
  +0x400=0  +0x470=64  +0x4b0=0  +0x4b8=1  +0x4ba=1  +0x7a0=0  +0x7f0=0  +0x1a8=0

Now check the OTHER candidate: what does ADOPTED ctx (0x3008954BD80) look
like at those offsets? We can't read it from here, but we can reason:
Enqueue's ctx has the queue at +0x10 (data@0x10, cap@0x18, widx@0x20,
count@0x24) — that's what LooksLikeQueue validated. So +0x4b0 of THAT
object would be queue-adjacent memory, not a component count.

`world` = holder[0] is the far better candidate: +0x470=64 and +0x4b8=1
look exactly like "64 archetypes, 1 of something".

DECISION: pass the `store` (holder) to the transformer, which we already do.
The only remaining question is whether calling the transformer at all is safe.
Let's dump more of `world` to be sure it is the ECS registry: check
+0x746350 region reachability and +0xe15350 (programCount) that the registrar
touches, since the registrar's rcx is the same registry.
"""
import struct
import sys

sys.path.insert(0, r"E:\DSH\肥鱼乐园\WolfMount\tools")
print("holder=0x815A0DBA30 world=0x815A0DBA40 (holder+0x10)")
print("registrar 0x1409d5770 uses rcx+0x746350 (program slots) and rcx+0xe15350")
print("=> if `world` is the registry, world+0x746350 and world+0xe15350 must be readable")
print("world+0x746350 = 0x815A0DBA40 + 0x746350 = 0x815AB52E90")
print("world+0xe15350 = 0x815A0DBA40 + 0xe15350 = 0x815B8F0D90")
print("both inside the same heap region -> plausible")
