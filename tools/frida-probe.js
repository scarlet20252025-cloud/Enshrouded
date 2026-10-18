// WolfMount runtime probe.
// Goal: find the ECS world pointer and the local player's entityId + world position.
//
// Strategy (derived from static analysis of enshrouded.exe, build 1267041):
//   1. Hook SendEvent (rva 0x955400) and log every type hash + the ctx pointer.
//   2. Hook GetEntityId (rva 0x9b6a20): `eax = *(u16*)(rcx+0xb8)`.
//      This is called with rcx = an object; +0xb8 holds a u16 entity id.
//      The same object's +0x1b8 holds the event buffer (GetEventBuf 0x9b85d0).
//      So whenever we see a call, we can dump the whole object and look for
//      structure: what is at +0x00, +0x98, +0xb8, +0x1b8, etc.
//   3. Hook ResolveEnt (rva 0x9b2e40) which takes (rcx=handle, rdx=out, r8=out2)
//      and does a two-level table lookup. rcx+0 is a pointer, rcx+8 is an index,
//      *(rcx+0)+0x828 is a table of u32 -> that is the ECS entity storage.
//      => **rcx+0 at the time of the call points to a structure whose +0x828
//         is the entity table.** Dump around it to find the world pointer.
//
// All addresses are RVA offsets from the module base.

const BASE_OFF = {
  SendEvent:   0x955400,
  SendEventEx: 0x954250,
  Enqueue:     0x952400,
  GetEntityId: 0x9b6a20,
  GetEventBuf: 0x9b85d0,
  ResolveEnt:  0x9b2e40,
};

function main() {
  const mod = Process.enumerateModules().find(m => m.name.toLowerCase().includes('enshrouded'));
  if (!mod) {
    console.log('[!] enshrouded module not found');
    return;
  }
  const base = mod.base;
  console.log('[+] enshrouded base = ' + base);

  function addr(name) { return base.add(BASE_OFF[name]); }

  // ---- 1. ResolveEnt: find the entity table root -------------------------
  // void* ResolveEnt(void* rcx, void* rdx /*out ptr*/, u32* r8 /*out id*/)
  //   eax = *(u32*)(rcx+8)          ; index
  //   if (eax == 0) { *rdx = 0; return rdx; }
  //   rax = *(u64*)rcx              ; -> level-1 table
  //   rcx = *(u64*)(rax+0x828)      ; -> level-2 table
  //   eax = *(u32*)(rcx + (eax-1)*8)
  //   *r8 = eax; return r8
  let resolveCount = 0;
  const seenRoots = {};
  Interceptor.attach(addr('ResolveEnt'), {
    onEnter(args) {
      this.rcx = args[0];
      this.idx = this.rcx.add(8).readU32();
      if (this.idx === 0) return;
      try {
        this.l1 = this.rcx.readPointer();
        this.l2 = this.l1.add(0x828).readPointer();
        // read the resolved u32 to prove the chain works
        const resolved = this.l2.add((this.idx - 1) * 8).readU32();
        this.resolved = resolved;
      } catch (e) { return; }
      resolveCount++;
      if (resolveCount <= 40) {
        const k = this.l1.toString();
        if (!seenRoots[k]) {
          seenRoots[k] = 0;
          console.log('[ResolveEnt] l1=' + k +
                      ' l2=' + this.l2.toString() +
                      ' idx=' + this.idx +
                      ' resolved=0x' + this.resolved.toString(16));
        }
        seenRoots[k]++;
      }
    }
  });
  console.log('[+] hooked ResolveEnt, distinct roots will be printed as they appear');

  // ---- 2. GetEntityId: dump the calling object ---------------------------
  // u16 GetEntityId(void* rcx) { return *(u16*)(rcx+0xb8); }
  let eidCount = 0;
  const eidSeen = {};
  Interceptor.attach(addr('GetEntityId'), {
    onEnter(args) {
      eidCount++;
      if (eidCount > 300) return;
      try {
        const o = args[0];
        const id = o.add(0xb8).readU16();
        const key = o.toString();
        if (eidSeen[key]) return;
        eidSeen[key] = 1;
        // dump first 0x1d0 bytes as hex
        let s = '';
        for (let i = 0; i < 0x1e0; i += 8) {
          s += ' +' + i.toString(16).padStart(3, '0') + ':' + o.add(i).readPointer().toString(16);
        }
        console.log('[EidObj] ' + key + ' eid=' + id + '\n   ' + s);
      } catch (e) {}
    }
  });
  console.log('[+] hooked GetEntityId');

  // ---- 3. SendEvent: log type hashes + ctx -------------------------------
  let seCount = 0;
  Interceptor.attach(addr('SendEvent'), {
    onEnter(args) {
      seCount++;
      if (seCount > 400) return;
      // void* SendEvent(void* buf, u32 typeHash, u32 size, u32 entityId)
      const buf = args[0], hash = args[1].toUInt32(), size = args[2].toUInt32(), eid = args[3].toUInt32();
      if (seCount <= 200) {
        console.log('[SendEvent] hash=0x' + hash.toString(16).padStart(8, '0') +
                    ' size=' + size + ' eid=' + eid + ' buf=' + buf.toString());
      }
    }
  });
  console.log('[+] hooked SendEvent');

  // ---- 4. Enqueue: same but for the flags=3 component-write path ----------
  // SetIsTame -> Enqueue(ctx, u64*, ...) writes IsTame. Log all of them.
  let enqCount = 0;
  Interceptor.attach(addr('Enqueue'), {
    onEnter(args) {
      enqCount++;
      if (enqCount > 300) return;
      if (enqCount <= 150) {
        console.log('[Enqueue] rcx=' + args[0].toString() +
                    ' rdx=' + args[1].toString() +
                    ' r8=0x' + args[2].toUInt32().toString(16) +
                    ' r9=' + args[3].toUInt32());
      }
    }
  });
  console.log('[+] hooked Enqueue');
  console.log('[=] probe running; wait ~15s of gameplay then read this log');
}

setTimeout(main, 3000);
