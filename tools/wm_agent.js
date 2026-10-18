// WolfMount Frida agent v2 — safe, hook-minimal, RPC driven.
//
// Crash post-mortem (2026-10-17): killing the frida CLI left Interceptor's
// inline patches dangling inside the game -> ucrtbase access violation.
// Rules enforced here:
//   * The driver ALWAYS session.detach(); nothing is ever killed.
//   * Every hook is either long-lived-and-cheap (SendEvent) or briefly armed
//     and self-detaching (captureCtx).
//   * Every target read is guarded by try/catch.
//   * No writes to target memory.

const OFF = {
  SendEvent:   0x955400,
  GetEntityId: 0x9b6a20,
};

let mod = null, base = null;
let seHook = null;
let collected = [];
let seenKeys = {};
const MAX_EVENTS = 6000;

function init() {
  mod = Process.enumerateModules().find(m => m.name.toLowerCase().includes('enshrouded'));
  if (!mod) throw new Error('enshrouded module not found');
  base = mod.base;
  return { base: base.toString(), size: mod.size };
}

// ---------- guarded readers ------------------------------------------------
function u16(p) { try { return p.readU16(); } catch (e) { return -1; } }
function u32(p) { try { return p.readU32(); } catch (e) { return -1; } }
function u64(p) { try { return p.readU64().toString(10); } catch (e) { return null; } }
function ptrAt(p) { try { const v = p.readPointer(); return v.isNull() ? null : v; } catch (e) { return null; } }
function f32(p) { try { return p.readFloat(); } catch (e) { return null; } }
function f64(p) { try { return p.readDouble(); } catch (e) { return null; } }

// ---------- SendEvent hook -------------------------------------------------
function start() {
  if (seHook) return { already: true };
  seHook = Interceptor.attach(base.add(OFF.SendEvent), {
    onEnter(args) {
      if (collected.length >= MAX_EVENTS) return;
      try {
        const hash = args[1].toUInt32();
        const eid = args[3].toUInt32();
        const k = hash + ':' + eid;
        const c = seenKeys[k] = (seenKeys[k] || 0) + 1;
        if (c <= 3) {
          collected.push({
            hash: hash,
            eid: eid,
            size: args[2].toUInt32(),
            buf: args[0].toString(),
          });
        }
      } catch (e) {}
    }
  });
  return { armed: true, at: base.add(OFF.SendEvent).toString() };
}

function stop() {
  if (seHook) { try { seHook.detach(); } catch (e) {} seHook = null; }
  return { detached: true };
}

function events(limit) { return collected.slice(0, limit || 500); }
function resetEvents() { collected = []; seenKeys = {}; return { ok: true }; }

function stats() {
  const agg = {};
  for (const e of collected) {
    const k = e.hash + ':' + e.size;
    const a = agg[k] = agg[k] || { hash: e.hash, size: e.size, n: 0, eids: {} };
    a.n++;
    a.eids[e.eid] = (a.eids[e.eid] || 0) + 1;
  }
  return Object.keys(agg).map(k => ({
    hash: agg[k].hash, size: agg[k].size, n: agg[k].n,
    eids: Object.keys(agg[k].eids).map(Number)
  })).sort((a, b) => b.n - a.n);
}

// ---------- bounded GetEntityId capture ------------------------------------
// Briefly hook GetEntityId, whose only job is `return *(u16*)(rcx + 0xb8)`.
// We record every distinct object whose id equals `eid`, then detach at once.
function captureCtx(eid, timeoutMs) {
  return new Promise(resolve => {
    const hits = new Set();
    let calls = 0, done = false;
    const want = eid & 0xffff;

    const finish = () => {
      if (done) return;
      done = true;
      try { h.detach(); } catch (e) {}
      clearTimeout(timer);
      resolve({ eid: want, calls: calls, hits: Array.from(hits) });
    };

    const h = Interceptor.attach(base.add(OFF.GetEntityId), {
      onEnter(args) {
        calls++;
        try {
          if (args[0].add(0xb8).readU16() === want) {
            hits.add(args[0].toString());
            // enough evidence; stop immediately to minimise exposure
            if (hits.size >= 8) finish();
          }
        } catch (e) {}
      }
    });
    const timer = setTimeout(finish, timeoutMs || 15000);
  });
}

// ---------- structure survey of an object ----------------------------------
// Reports a compact field map: for each 8-byte slot, the pointer target and
// whether it is readable, plus any slot that decodes as a plausible float3.
function survey(addrStr, len) {
  const p = ptr(addrStr);
  len = len || 0x400;
  const rows = [];
  for (let i = 0; i + 8 <= len; i += 8) {
    const v = ptrAt(p.add(i));
    rows.push({
      off: i,
      ptr: v ? v.toString() : null,
      readable: v ? (function () { try { v.readU8(); return true; } catch (e) { return false; } })() : false,
      u32lo: u32(p.add(i)),
      u32hi: u32(p.add(i + 4)),
      f32lo: f32(p.add(i)),
      f64: f64(p.add(i)),
    });
  }
  return rows;
}

// Scan an object for a WorldPosition-like triple: 3 consecutive int64 in a
// plausible world-coordinate range, or 3 consecutive floats in range.
function findCoords(addrStr, len) {
  const p = ptr(addrStr);
  len = len || 0x400;
  const out = [];
  for (let i = 0; i + 24 <= len; i += 4) {
    const a = f32(p.add(i)), b = f32(p.add(i + 4)), c = f32(p.add(i + 8));
    if (a === null || b === null || c === null) continue;
    const ok = [a, b, c].every(x => isFinite(x) && Math.abs(x) > 0.5 && Math.abs(x) < 200000);
    // require not-all-equal and a spread, to reject repeated padding values
    if (ok && !(Math.abs(a - b) < 0.001 && Math.abs(b - c) < 0.001)) {
      out.push({ off: i, kind: 'f32x3', v: [a, b, c] });
    }
  }
  for (let i = 0; i + 24 <= len; i += 4) {
    const a = u64(p.add(i)), b = u64(p.add(i + 8)), c = u64(p.add(i + 16));
    if (a === null || b === null || c === null) continue;
    const A = Number(a), B = Number(b), C = Number(c);
    if ([A, B, C].every(x => Math.abs(x) < 2e6) && (Math.abs(A) + Math.abs(B) + Math.abs(C)) > 10) {
      out.push({ off: i, kind: 'i64x3', v: [A, B, C] });
    }
  }
  return out;
}

// Search an object for runs that look like EntityComponentEntry
// {u16 index, u16 offset, u16 size}: index < 12646, size <= 2184,
// offsets strictly increasing.
function findComponentTable(addrStr, len) {
  const p = ptr(addrStr);
  len = len || 0x400;
  const out = [];
  for (const stride of [6, 8]) {
    for (let start = 0; start + stride * 8 <= len; start += 2) {
      let prevOff = -1, ok = true;
      const ents = [];
      for (let e = 0; e < 24; e++) {
        const o = start + e * stride;
        if (o + 6 > len) { ok = ents.length >= 8; break; }
        const idx = u16(p.add(o));
        const off = u16(p.add(o + 2));
        const sz = u16(p.add(o + 4));
        if (idx < 0 || idx >= 12646 || off < 0 || off > 0x8000 || sz <= 0 || sz > 2184 || off <= prevOff) {
          ok = ents.length >= 8; break;
        }
        prevOff = off;
        ents.push([idx, off, sz]);
      }
      if (ok && ents.length >= 8) {
        out.push({ stride: stride, start: start, count: ents.length, entries: ents });
      }
    }
  }
  return out.slice(0, 12);
}

function dump(addrStr, len) {
  const p = ptr(addrStr);
  len = len || 0x200;
  const lines = [];
  for (let i = 0; i < len; i += 16) {
    let hex = '', asc = '';
    for (let j = 0; j < 16; j++) {
      let b = 0;
      try { b = p.add(i + j).readU8(); } catch (e) { hex += '?? '; asc += '?'; continue; }
      hex += b.toString(16).padStart(2, '0') + ' ';
      asc += (b >= 32 && b < 127) ? String.fromCharCode(b) : '.';
    }
    lines.push('+' + i.toString(16).padStart(4, '0') + '  ' + hex + ' |' + asc + '|');
  }
  return lines;
}

function probe(addrStr, len) {
  try { ptr(addrStr).readByteArray(len || 8); return true; } catch (e) { return false; }
}

rpc.exports = {
  init: init,
  start: start,
  stop: stop,
  events: events,
  resetEvents: resetEvents,
  stats: stats,
  captureCtx: captureCtx,
  survey: survey,
  findCoords: findCoords,
  findComponentTable: findComponentTable,
  dump: dump,
  probe: probe,
};
