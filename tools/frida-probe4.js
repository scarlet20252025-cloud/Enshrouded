// Phase 4: from the confirmed player entity context (eid=570 at l1=0x9cbd8dbae0
// in the previous run), find:
//   1. the entity's WorldPosition (three sint64 at some offset in a component)
//   2. the component table: EntityComponentEntry arrays indexed by component id
//
// What we know about the object at l1 (the "entity context"):
//   +0x000  ptr 3006bed4b40   (component storage? - appears also at +0x30,+0x38)
//   +0x008  ptr 3008954bd80
//   +0x010  ptr 1001dbe13a0   (this is 0x1dbe13a0 - a LOW address: inside the
//                               game module's data region? module base+0x19d13a0)
//   +0x018  ptr 3008b8f1568
//   +0x020  ptr 3006bed4d38
//   +0x028  ptr 30096b05b68
//   +0x040  0x2800000028  -> low u32 = 0x28 (40), high u32 = 0x28 (40)  << count!
//   +0x048  ptr 3006cdb2a00
//   +0x050  0x00fe502b     -> looks like {u16 count, u16 ...}
//   +0x058  0x02faf081
//   +0x060  0x04883049
//   +0x068  0x25d800000001
//   +0x070  0x0895000025d4
//   +0x078  0x0259829db48
//   +0x0a8  ptr 7ff74bf91ab8  (module .data)
//   +0x0b0  u32 0x11 = 17
//   +0x0b8  u16 entityId = 570  (0x23a)
//   +0x0ba  u32 0x00000000
//   +0x0c0..+0x150  ptrs (mostly self + 3006bc...)
//   +0x158  0x68 = 104
//   +0x180  float 0x3d888889 ~ 0.0667
//   +0x190  ptr 9cbd8dbeb0  (self+0x3d0)
//   +0x1b8  ptr 300895519a8  = event buffer
//   +0x300  0
//   +0x308  ptr 9cbd8dbe60 (self+0x380)
//   +0x310  1
//
// Plan:
//   a) Re-find the player entity context live (GetEntityId + most-frequent
//      NoiseEvent eid), then dump it, and ALSO dereference +0x000 (3006bed4b40)
//      which is likely the component array.
//   b) Dump the array at +0x000: it probably is EntityComponentEntry[]
//      {u16 index, u16 offset, u16 size} repeated.  Verify by checking that
//      index values are < 12646 and offsets are increasing.
//   c) Use the reflection table to map index -> type name, and read the
//      CurrentTransform component (index 881) to get the world position.

const OFF = { ResolveEnt: 0x9b2e40, GetEntityId: 0x9b6a20, GetEventBuf: 0x9b85d0 };

function main() {
  const mod = Process.enumerateModules().find(m => m.name.toLowerCase().includes('enshrouded'));
  if (!mod) { console.log('[!] no module'); return; }
  const base = mod.base;
  const MEND = mod.base.add(mod.size);
  console.log('[+] base ' + base + ' end ' + MEND);

  // ---- 1. identify the player entity context -----------------------------
  let playerEid = -1;
  const se = Interceptor.attach(base.add(0x955400), {
    onEnter(args) {
      if (args[1].toUInt32() === 0xd079d101) { playerEid = args[3].toUInt32(); }
    }
  });
  setTimeout(() => {
    se.detach();
    console.log('[+] player eid = ' + playerEid);
    if (playerEid < 0) return;

    // capture the object that owns this eid
    let playerCtx = null;
    const ge = Interceptor.attach(base.add(OFF.GetEntityId), {
      onEnter(args) {
        try {
          const o = args[0];
          const id = o.add(0xb8).readU16();
          if (id === playerEid) { playerCtx = o; ge.detach(); }
        } catch (e) {}
      }
    });

    setTimeout(() => {
      if (!playerCtx) { console.log('[!] player ctx not found'); return; }
      console.log('[+] player ctx = ' + playerCtx);
      dumpObj(playerCtx, 0x420, 'CTX');

      // ---- 2. dereference +0x000 (component storage) --------------------
      const store = playerCtx.add(0x000).readPointer();
      console.log('[+] ctx+0x000 = ' + store);
      dumpObj(store, 0x200, 'STORE');

      // +0x030 / +0x038 also pointed to the same store in the previous dump
      for (const off of [0x030, 0x038, 0x008, 0x018, 0x020, 0x028, 0x0c0, 0x0c8, 0x1b8]) {
        try {
          const p = playerCtx.add(off).readPointer();
          console.log('  ctx+' + off.toString(16) + ' = ' + p);
        } catch (e) {}
      }

      // ---- 3. Look for EntityComponentEntry arrays ----------------------
      // Entry = {u16 index, u16 offset, u16 size} (6 bytes) or maybe 8 bytes.
      // Scan the ctx and the store for runs where:
      //   entry.index < 12646, entry.offset < 0x4000, entry.size <= 2184
      //   and offsets are strictly increasing.
      console.log('=== scanning ctx and store for component entry arrays ===');
      for (const [label, obj, len] of [['ctx', playerCtx, 0x420], ['store', store, 0x200]]) {
        try {
          const b = obj.readByteArray(len);
          const u8 = new Uint8Array(b);
          const dv = new DataView(b);
          let best = null;
          for (let stride = 6; stride <= 8; stride += 2) {
            for (let start = 0; start + stride * 12 < len; start += stride) {
              let ok = true, prevOff = -1;
              const comps = [];
              for (let e = 0; e < 12; e++) {
                const o = start + e * stride;
                const idx = dv.getUint16(o, true);
                const off = dv.getUint16(o + 2, true);
                const sz  = dv.getUint16(o + 4, true);
                if (idx >= 12646 || sz > 2184 || off > 0x8000 || off <= prevOff) { ok = false; break; }
                prevOff = off;
                comps.push(idx + ':' + off + ':' + sz);
              }
              if (ok) {
                const cand = { label, stride, start, comps };
                if (!best || cand.comps.length > best.comps.length) best = cand;
              }
            }
          }
          if (best) {
            console.log('  [' + label + '] FOUND entry array stride=' + best.stride + ' at +0x' + best.start.toString(16));
            console.log('    comps: ' + best.comps.join(' '));
          } else {
            console.log('  [' + label + '] no plausible entry array');
          }
        } catch (e) { console.log('  [' + label + '] read failed: ' + e); }
      }

      // ---- 4. Read CurrentTransform (reflection idx 881, size 56) --------
      // Component storage is probably a big byte array at `store`; component
      // data lives at store + entry.offset. We don't know the layout yet, so
      // instead: scan the ctx/store for a WorldPosition-like triple of
      // sint64 values that are large-ish but plausible world coords
      // (Enshrouded world coords are roughly +/- 100000).
      console.log('=== scanning for WorldPosition (3x sint64) in ctx/store ===');
      for (const [label, obj, len] of [['ctx', playerCtx, 0x420], ['store', store, 0x400]]) {
        try {
          const b = obj.readByteArray(len);
          const dv = new DataView(b);
          for (let o = 0; o + 24 <= len; o += 4) {
            const x = dv.getBigInt64(o, true);
            const y = dv.getBigInt64(o + 8, true);
            const z = dv.getBigInt64(o + 16, true);
            const lim = 400000n;
            if (x > -lim && x < lim && y > -lim && y < lim && z > -lim && z < lim &&
                (x !== 0n || y !== 0n || z !== 0n)) {
              const fx = Number(x), fy = Number(y), fz = Number(z);
              if (Math.abs(fx) + Math.abs(fy) + Math.abs(fz) > 100) {
                console.log('  [' + label + '] +0x' + o.toString(16) +
                            ' WorldPosition(' + fx + ', ' + fy + ', ' + fz + ')');
              }
            }
          }
        } catch (e) {}
      }
    }, 3000);
  }, 5000);
}

function dumpObj(o, len, label) {
  console.log('---- dump ' + label + ' ' + o + ' ----');
  let s = '';
  for (let i = 0; i < len; i += 8) {
    let v;
    try { v = o.add(i).readPointer().toString(16); } catch (e) { v = 'xx'; }
    s += ' +' + i.toString(16).padStart(3, '0') + ':' + v;
    if ((i & 0x3f) === 0x38) { console.log(s); s = ''; }
  }
  if (s) console.log(s);
}

setTimeout(main, 1500);
