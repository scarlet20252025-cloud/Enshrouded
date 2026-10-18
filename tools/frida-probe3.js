// Phase 3: map the ECS entity store using the two live roots we already found.
//
// Live observations (from frida-probe.log):
//   root A: l1 = 0x9cbd8dda30, l2 = 0x300800e4e40, idx=1 -> resolved=0xe4040314
//   root B: l1 = 0x9cbd8dbc20, l2 = 0x300800bf640, idx=1 -> resolved=0xe4040002
//   object at l1 has +0xb8 = u16 entityId (142 / 570)
//   object at l1 has +0x1b8 = event buffer   (SendEvent buf arg)
//
// So the object at 'l1' IS the per-entity/world context. Its:
//   +0x000 -> itself-ish/other pointer
//   +0x828 -> level-2 entity id table
//   +0x0b8 -> u16 entity id of the owner
//   +0x1b8 -> event buffer used by SendEvent
//
// Strategy:
//   1. Re-discover these roots live (do not hardcode addresses).
//   2. Dump the full object (0x000..0x400) for both roots.
//   3. Walk the level-2 table: for i in 0..N read *(u32*)(l2 + i*8) -> resolved id.
//      Also treat l2 as an array of 8-byte slots and read them as entityIds.
//   4. Look for the player: the object whose +0xb8 matches the SendEvent eid we
//      see most (player is the source of NoiseEvent spam -> eid=570 or 142).
//   5. Dump candidate 'player' object fields looking for WorldPosition
//      (three sint64) or float3, and for the reflection-table pointer.

const OFF = {
  ResolveEnt:  0x9b2e40,
  GetEntityId: 0x9b6a20,
  GetEventBuf: 0x9b85d0,
};

function main() {
  const mod = Process.enumerateModules().find(m => m.name.toLowerCase().includes('enshrouded'));
  if (!mod) { console.log('[!] no module'); return; }
  const base = mod.base;
  console.log('[+] base ' + base);

  const roots = new Map(); // l1 -> {l2, samples}

  Interceptor.attach(base.add(OFF.ResolveEnt), {
    onEnter(args) {
      try {
        const rcx = args[0];
        const idx = rcx.add(8).readU32();
        if (idx === 0) return;
        const l1 = rcx.readPointer();
        if (l1.isNull()) return;
        const l2 = l1.add(0x828).readPointer();
        if (l2.isNull()) return;
        if (!roots.has(l1.toString())) roots.set(l1.toString(), { l1: l1, l2: l2, n: 0, idxMin: 1e9, idxMax: 0 });
        const r = roots.get(l1.toString());
        r.n++;
        r.idxMin = Math.min(r.idxMin, idx);
        r.idxMax = Math.max(r.idxMax, idx);
      } catch (e) {}
    }
  });

  setTimeout(() => {
    console.log('==== distinct ResolveEnt roots: ' + roots.size + ' ====');
    for (const [k, r] of roots) {
      console.log('  l1=' + k + ' l2=' + r.l2.toString() + ' calls=' + r.n +
                  ' idx=' + r.idxMin + '..' + r.idxMax);
    }

    // Full dump of each root object
    for (const [k, r] of roots) {
      console.log('---- FULL DUMP root ' + k + ' ----');
      let s = '';
      for (let i = 0; i < 0x400; i += 8) {
        let v;
        try { v = r.l1.add(i).readPointer().toString(16); } catch (e) { v = 'xx'; }
        s += ' +' + i.toString(16).padStart(3, '0') + ':' + v;
        if ((i & 0x3f) === 0x38) { console.log(s); s = ''; }
      }
      if (s) console.log(s);

      // Walk the level-2 table: read u32 at l2 + i*8 for a while
      console.log('---- l2 table walk ' + r.l2.toString() + ' ----');
      const ids = [];
      for (let i = 0; i < 64; i++) {
        try { ids.push(r.l2.add(i * 8).readU32()); } catch (e) { break; }
      }
      console.log('  first 64 slots: ' + ids.join(','));
      const nz = ids.filter(x => x !== 0);
      console.log('  non-zero: ' + nz.length + '/' + ids.length);
    }

    // Now: find which root belongs to the local player.
    // The SendEvent spam (NoiseEvent, eid=X) comes from the player entity.
    // We recorded nothing about eid in this run, so re-hook SendEvent briefly.
    let playerEid = -1;
    const se = Interceptor.attach(base.add(0x955400), {
      onEnter(args) {
        const h = args[1].toUInt32();
        if (h === 0xd079d101) { playerEid = args[3].toUInt32(); se.detach(); }
      }
    });
    setTimeout(() => {
      console.log('==== player eid (from NoiseEvent spam) = ' + playerEid + ' ====');
      // Cross-check: hook GetEntityId and record which object yields that id
      Interceptor.attach(base.add(OFF.GetEntityId), {
        onEnter(args) {
          try {
            const o = args[0];
            const id = o.add(0xb8).readU16();
            if (id === playerEid) {
              console.log('[PLAYER OBJECT] ' + o.toString() + ' eid=' + id);
              let s = '';
              for (let i = 0; i < 0x300; i += 8) {
                let v; try { v = o.add(i).readPointer().toString(16); } catch (e) { v = 'xx'; }
                s += ' +' + i.toString(16).padStart(3, '0') + ':' + v;
                if ((i & 0x3f) === 0x38) { console.log(s); s = ''; }
              }
              if (s) console.log(s);
              // try to read floats at many offsets
              const fv = [];
              for (let i = 0; i < 0x300; i += 4) {
                try { const f = o.add(i).readFloat(); if (isFinite(f) && Math.abs(f) > 0.001 && Math.abs(f) < 1e7) fv.push('+' + i.toString(16) + '=' + f.toFixed(2)); } catch (e) {}
              }
              console.log('  floats: ' + fv.join(' '));
            }
          } catch (e) {}
        }
      });
      console.log('[+] GetEntityId armed for player eid ' + playerEid);
    }, 4000);
  }, 8000);
}

setTimeout(main, 1500);
