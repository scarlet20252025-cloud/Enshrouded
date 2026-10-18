"""WolfMount recon v2: identify the player entity context and its components.

Player identification: the local player is the entity that appears across the
most *distinct* message types (it emits flying, hit, noise, buff, toggle events
all with the same eid).  We then briefly arm GetEntityId to capture the object
whose +0xb8 equals that eid, and survey it.

Always detaches cleanly.
"""
import sys, io, os, time, json
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import frida

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, "wm_agent.js")


def find_pid():
    for p in frida.get_local_device().enumerate_processes():
        if "enshrouded" in p.name.lower():
            return p.pid
    return None


def main():
    pid = find_pid()
    if not pid:
        print("[!] game not running")
        return 1
    print(f"[+] attach pid {pid}")
    session = frida.attach(pid)
    script = session.create_script(open(AGENT, encoding="utf-8").read())
    script.on("message", lambda m, d: print("[agent]", m.get("description") or m.get("payload")))
    script.load()
    api = script.exports_sync
    out = {}

    try:
        info = api.init()
        print(f"[+] base {info['base']} size 0x{info['size']:x}")
        api.start()

        print("[=] waiting for in-world traffic (240s max)...")
        ev = []
        for i in range(240):
            time.sleep(1)
            ev = api.events(6000)
            if len(ev) >= 40:
                print(f"[+] {len(ev)} events after {i+1}s")
                break
            if i % 20 == 19:
                print(f"    ...{i+1}s, {len(ev)} events")
        api.stop()
        if len(ev) < 40:
            print("[!] not enough traffic")
            return 2

        st = api.stats()
        print("\n==== message types ====")
        print(f"{'hash':>10}  {'size':>6}  {'n':>5}  eids")
        for r in st:
            print(f"0x{r['hash']:08X}  {r['size']:6d}  {r['n']:5d}  {r['eids'][:10]}")

        # player = eid appearing across the most distinct message types
        typecount = Counter()
        total = Counter()
        for e in ev:
            typecount[e["eid"]] += 0  # placeholder
        seen = {}
        for e in ev:
            key = (e["hash"], e["eid"])
            if key in seen:
                continue
            seen[key] = 1
            typecount[e["eid"]] += 1
        for e in ev:
            total[e["eid"]] += 1
        print("\n==== entity score (distinct types, total events) ====")
        for eid, nt in typecount.most_common(12):
            print(f"  eid {eid:6d}  types={nt:3d}  events={total[eid]:5d}")
        peid = typecount.most_common(1)[0][0]
        print(f"\n[+] player eid = {peid}")
        out["player_eid"] = peid
        out["types"] = st

        # ---- capture the context object ------------------------------
        print(f"[=] briefly arming GetEntityId to catch +0xb8 == {peid}")
        cap = api.captureCtx(peid, 20000)
        print(f"[+] capture: calls={cap['calls']} hits={cap['hits']}")
        out["ctx_hits"] = cap["hits"]
        if not cap["hits"]:
            print("[!] no context captured")
            return 3

        for ctx in cap["hits"][:3]:
            print(f"\n================ CTX {ctx} ================")
            rows = api.survey(ctx, 0x400)
            for r in rows:
                if r["ptr"] or (r["u32lo"] not in (0, None)):
                    mark = "R" if r["readable"] else " "
                    print(f"  +{r['off']:04x} {mark} ptr={str(r['ptr']):>18}  u32={r['u32lo']},{r['u32hi']}  f32={r['f32lo']}")

            print(f"---- coords in {ctx} ----")
            for c in api.findCoords(ctx, 0x400):
                print(f"  +{c['off']:04x} {c['kind']} {c['v']}")

    finally:
        print("[+] detaching cleanly")
        try: api.stop()
        except Exception: pass
        try: session.detach()
        except Exception: pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
