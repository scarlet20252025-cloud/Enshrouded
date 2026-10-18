// Phase 2 probe: with the game already in-world and Frida attached, do a
// memory scan for the ECS world / player structures.
//
// Key insight from static analysis:
//   GetEntityId(rcx):  return *(u16*)(rcx + 0xb8)
//   GetEventBuf(rcx):  return *(u64*)(rcx + 0x1b8)
//   => there is an object where +0xb8 = u16 entityId and +0x1b8 = event buffer
//   ResolveEnt(rcx, rdx, r8):
//     eax = *(u32*)(rcx+8)        // index
//     l1 = *(u64*)rcx             // level-1 table
//     l2 = *(u64*)(l1 + 0x828)    // level-2 table
//     *(u32*)(l2 + (eax-1)*8)     // resolved id
//
// We scan the heap for a pointer P such that:
//   *(u64*)(P + 0x828) is a readable pointer, and
//   at least one of *(u32*)(P + 8) resolves via the two-level table.
// That P is the ECS entity-store root -> a candidate world pointer.

const BASE_OFF = {
  ResolveEnt:  0x9b2e40,
  GetEntityId: 0x9b6a20,
  GetEventBuf: 0x9b85d0,
};

function main() {
  const mod = Process.enumerateModules().find(m => m.name.toLowerCase().includes('enshrouded'));
  if (!mod) { console.log('[!] no module'); return; }
  const base = mod.base;
  console.log('[+] base ' + base);

  // ---------- A. Scan heap memory for the ResolveEnt root pattern ----------
  // Pattern: any address A in a writable region where
  //   q = *(u64*)(A + 0x828) is a valid pointer AND
  //   *(u64*)(A) is a valid pointer (level-1 table)
  // We then verify by checking that *(u32*)(A+8) is small (entity index).
  console.log('[*] scanning writable memory for ResolveEnt roots...');
  const ranges = Process.enumerateRanges({ protection: 'rw', coalesce: true });
  let scanned = 0, found = 0;
  const roots = [];
  for (const r of ranges) {
    if (r.base.readPointer().equals(0)) continue;
    // skip tiny ranges
    if (r.size < 0x1000) continue;
    try {
      const len = Math.min(r.size, 0x200000); // cap per range
      const buf = r.base.readByteArray(len);
      if (!buf) continue;
      scanned += len;
      const u8 = new Uint8Array(buf);
      // We look for 8-byte slots in the *middle* of structures, i.e. we
      // cannot scan for pointers to unknown addresses. Instead, we use the
      // known hook data: capture actual rcx values at ResolveEnt and derive
      // the root from them.  (done in part B)
      // So part A just reports range stats.
    } catch (e) {}
  }
  console.log('[+] scanned ' + scanned + ' bytes of rw memory in ' + ranges.length + ' ranges');

  // ---------- B. Capture live rcx values from the hooks -------------------
  // Interceptor hooks are already installed by phase-1 script only if it is
  // still running.  In a fresh attach we install them here.
  const resolveSamples = [];
  Interceptor.attach(base.add(BASE_OFF.ResolveEnt), {
    onEnter(args) {
      try {
        const rcx = args[0];
        const idx = rcx.add(8).readU32();
        if (idx === 0) return;
        const l1 = rcx.readPointer();
        if (l1.isNull()) return;
        const l2 = l1.add(0x828).readPointer();
        if (l2.isNull()) return;
        const resolved = l2.add((idx - 1) * 8).readU32();
        if (resolveSamples.length < 200) {
          resolveSamples.push({
            rcx: rcx.toString(),
            l1: l1.toString(),
            l2: l2.toString(),
            idx: idx,
            resolved: resolved
          });
        }
      } catch (e) {}
    }
  });
  console.log('[+] ResolveEnt capture armed');

  const eidSamples = [];
  Interceptor.attach(base.add(BASE_OFF.GetEntityId), {
    onEnter(args) {
      try {
        const o = args[0];
        const id = o.add(0xb8).readU16();
        if (eidSamples.length < 200) {
          eidSamples.push({ obj: o.toString(), eid: id });
        }
      } catch (e) {}
    }
  });
  console.log('[+] GetEntityId capture armed');

  // dump everything after 6 seconds
  setTimeout(() => {
    console.log('==== ResolveEnt samples: ' + resolveSamples.length + ' ====');
    const byL1 = {};
    for (const s of resolveSamples) {
      (byL1[s.l1] = byL1[s.l1] || []).push(s);
    }
    for (const l1 in byL1) {
      const arr = byL1[l1];
      console.log('  l1=' + l1 + '  samples=' + arr.length +
                  '  l2=' + arr[0].l2 +
                  '  idx range=' + Math.min(...arr.map(x=>x.idx)) + '..' + Math.max(...arr.map(x=>x.idx)) +
                  '  resolved range=' + Math.min(...arr.map(x=>x.resolved)) + '..' + Math.max(...arr.map(x=>x.resolved)));
      // dump the rcx object of the first sample fully
      try {
        const rcx = ptr(arr[0].rcx);
        let s = '';
        for (let i = 0; i < 0x40; i += 8) {
          s += ' +' + i.toString(16).padStart(2,'0') + ':' + rcx.add(i).readPointer().toString(16);
        }
        console.log('    rcx@' + arr[0].rcx + ' => ' + s);
      } catch (e) {}
      // dump l1 around +0x828
      try {
        const p = ptr(l1);
        let s = '';
        for (let i = 0x800; i <= 0x860; i += 8) {
          s += ' +' + i.toString(16) + ':' + p.add(i).readPointer().toString(16);
        }
        console.log('    l1+0x800..0x860 => ' + s);
      } catch (e) {}
    }

    console.log('==== GetEntityId samples: ' + eidSamples.length + ' ====');
    const byObj = {};
    for (const s of eidSamples) (byObj[s.obj] = byObj[s.obj] || []).push(s);
    const objs = Object.keys(byObj);
    console.log('  distinct objects: ' + objs.length);
    for (let i = 0; i < Math.min(objs.length, 8); i++) {
      const o = ptr(objs[i]);
      const ids = byObj[objs[i]].map(x => x.eid);
      let s = '';
      try {
        for (let k = 0; k < 0x200; k += 8) {
          s += ' +' + k.toString(16).padStart(3,'0') + ':' + o.add(k).readPointer().toString(16);
        }
      } catch (e) {}
      console.log('  obj ' + objs[i] + ' eids=' + ids.slice(0,10).join(','));
      console.log('    ' + s);
    }
    // Print any object whose +0x1b8 is a plausible heap pointer
    console.log('==== objects with +0x1b8 non-null (event buffer) ====');
    let cnt = 0;
    for (const k of objs) {
      try {
        const o = ptr(k);
        const v = o.add(0x1b8).readPointer();
        if (!v.isNull()) {
          cnt++;
          if (cnt <= 6) console.log('  ' + k + ' +0x1b8 = ' + v.toString());
        }
      } catch (e) {}
    }
    console.log('  total: ' + cnt);
  }, 6000);
}

setTimeout(main, 2000);
