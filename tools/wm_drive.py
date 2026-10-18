"""WolfMount Frida driver.

Attaches to enshrouded.exe, loads wm_agent.js, and provides a REPL-ish CLI
over the RPC exports.  CRITICAL: always detach() cleanly -- never kill the
frida process, because Interceptor hooks are inline patches inside the game
and killing the agent leaves dangling jumps behind (that is what crashed the
game on 2026-10-17).
"""
import sys, io, os, time, json, argparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import frida

AGENT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wm_agent.js")


def find_pid(name="enshrouded"):
    for p in frida.get_local_device().enumerate_processes():
        if name.lower() in p.name.lower():
            return p.pid, p.name
    return None, None


class Session:
    def __init__(self, pid):
        self.pid = pid
        self.session = frida.attach(pid)
        self.script = self.session.create_script(open(AGENT, encoding="utf-8").read())
        self.script.on("message", self._on_message)
        self.script.load()

    def _on_message(self, message, data):
        if message.get("type") == "error":
            print("[agent error] " + str(message.get("description")), file=sys.stderr)
            print(message.get("stack", ""), file=sys.stderr)
        elif message.get("type") == "log":
            print("[agent] " + str(message.get("payload")))

    def __getattr__(self, name):
        return getattr(self.script.exports_sync, name)

    def close(self):
        try:
            self.script.exports_sync.stop()
        except Exception:
            pass
        try:
            self.session.detach()
        except Exception:
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["smoke", "events", "findctx", "dump", "probe", "qwords"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--pid", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    pid = a.pid
    if not pid:
        pid, nm = find_pid()
        if not pid:
            print("enshrouded.exe not running")
            return 1
    print(f"[+] attaching to pid {pid}")
    s = Session(pid)
    try:
        info = s.init()
        print(f"[+] module base {info['base']} size 0x{info['size']:x}")

        if a.cmd == "smoke":
            print("[+] arming SendEvent hook")
            print("    " + json.dumps(s.start()))
            print(f"[+] collecting for {a.seconds}s ...")
            time.sleep(a.seconds)
            ev = s.events(2000)
            print(f"[+] captured {len(ev)} sampled events")
            agg = {}
            for e in ev:
                k = (e["hash"], e["size"])
                agg.setdefault(k, [0, set()])
                agg[k][0] += 1
                if len(agg[k][1]) < 5:
                    agg[k][1].add(e["eid"])
            print(f"{'hash':>10}  {'size':>6}  {'n':>5}  eids")
            for (h, sz), (n, eids) in sorted(agg.items(), key=lambda x: -x[1][0]):
                print(f"0x{h:08X}  {sz:6d}  {n:5d}  {sorted(eids)}")
            print("    " + json.dumps(s.stop()))
            if a.out:
                json.dump(ev, open(a.out, "w", encoding="utf-8"), indent=1)
                print(f"[+] events written to {a.out}")

        elif a.cmd == "events":
            print("[+] arming")
            s.start()
            time.sleep(a.seconds)
            ev = s.events(int(a.args[0]) if a.args else 2000)
            s.stop()
            print(json.dumps(ev, indent=1))

        elif a.cmd == "findctx":
            buf, eid = a.args[0], int(a.args[1], 0)
            t0 = time.time()
            r = s.findCtx(buf, eid)
            print(f"[+] scanned {r['scanned']} bytes in {time.time()-t0:.1f}s")
            print(f"[+] matches: {r['matches']}")

        elif a.cmd == "dump":
            addr = a.args[0]
            ln = int(a.args[1], 0) if len(a.args) > 1 else 0x200
            for line in s.dump(addr, ln):
                print(line)

        elif a.cmd == "probe":
            print(s.probe(a.args[0], int(a.args[1], 0) if len(a.args) > 1 else 8))

        elif a.cmd == "qwords":
            addr = a.args[0]
            cnt = int(a.args[1]) if len(a.args) > 1 else 32
            st = int(a.args[2]) if len(a.args) > 2 else 8
            for row in s.qwords(addr, cnt, st):
                print(f"+{row['off']:04x}: {row['value']}")
    finally:
        print("[+] detaching cleanly")
        s.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
