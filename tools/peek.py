# -*- coding: utf-8 -*-
"""
peek.py - Enshrouded exe analysis helpers.

Usage:
  python peek.py sections
  python peek.py search <hexbytes> [--limit N]
  python peek.py hex <fileoffset> <len>
  python peek.py hexrva <rva> <len>
  python peek.py str <fileoffset> <len>
  python peek.py dword <fileoffset>
  python peek.py ptr <fileoffset>          # read u64, print as VA + rva
  python peek.py dis <va> <len>
  python peek.py findptr <va>              # find all pointers to this VA
  python peek.py reflect <name>            # dump type from reflection_data.json
"""
import sys, os, re, json, struct

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IMG = 0x140000000
SECS = []   # (name, va, vsize, raw, rawsize)

def load():
    global SECS
    if SECS:
        return
    with open(EXE, 'rb') as f:
        data = f.read()
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    nsec = struct.unpack_from('<H', data, pe + 6)[0]
    optsz = struct.unpack_from('<H', data, pe + 20)[0]
    off = pe + 24 + optsz
    for i in range(nsec):
        nm = data[off:off + 8].rstrip(b'\0').decode('latin1')
        vsize, va, rawsize, raw = struct.unpack_from('<IIII', data, off + 8)
        SECS.append((nm, va, vsize, raw, rawsize))
        off += 40

def rva2file(rva):
    load()
    for nm, va, vsize, raw, rawsize in SECS:
        if va <= rva < va + max(vsize, rawsize):
            return raw + (rva - va)
    return None

def file2rva(fo):
    load()
    for nm, va, vsize, raw, rawsize in SECS:
        if raw <= fo < raw + rawsize:
            return va + (fo - raw)
    return None

def va2file(va):
    return rva2file(va - IMG)

def read(fo, n):
    load()
    with open(EXE, 'rb') as f:
        f.seek(fo)
        return f.read(n)

def readrva(rva, n):
    return read(rva2file(rva), n)

def hexdump(b, base=0):
    out = []
    for i in range(0, len(b), 16):
        chunk = b[i:i + 16]
        h = ' '.join('%02x' % c for c in chunk)
        a = ''.join(chr(c) if 32 <= c < 127 else '.' for c in chunk)
        out.append('%08x  %-47s  %s' % (base + i, h, a))
    return '\n'.join(out)

def cstr(fo, maxlen=256):
    b = read(fo, maxlen)
    z = b.find(b'\0')
    if z >= 0:
        b = b[:z]
    return b.decode('latin1')

def search(pat, limit=50):
    load()
    with open(EXE, 'rb') as f:
        data = f.read()
    res = []
    start = 0
    while len(res) < limit:
        i = data.find(pat, start)
        if i < 0:
            break
        rva = file2rva(i)
        sec = None
        for nm, va, vsize, raw, rawsize in SECS:
            if raw <= i < raw + rawsize:
                sec = nm
        res.append((i, rva, sec))
        start = i + 1
    return res

def findptr(va, limit=50):
    return search(struct.pack('<Q', va), limit)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == 'sections':
        load()
        print('%-10s %-12s %-12s %-12s %-12s' % ('name', 'va', 'vsize', 'raw', 'rawsize'))
        for nm, va, vsize, raw, rawsize in SECS:
            print('%-10s %-12x %-12x %-12x %-12x' % (nm, va, vsize, raw, rawsize))
    elif cmd == 'search':
        pat = bytes.fromhex(sys.argv[2].replace(' ', ''))
        lim = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[3] == '--limit' else 50
        for fo, rva, sec in search(pat, lim):
            print('file 0x%X  rva 0x%X  [%s]' % (fo, rva or 0, sec or '?'))
    elif cmd == 'hex':
        print(hexdump(read(int(sys.argv[2], 0), int(sys.argv[3], 0)), int(sys.argv[2], 0)))
    elif cmd == 'hexrva':
        rva = int(sys.argv[2], 0)
        print('rva 0x%X -> file 0x%X' % (rva, rva2file(rva)))
        print(hexdump(readrva(rva, int(sys.argv[3], 0)), rva))
    elif cmd == 'str':
        print(repr(cstr(int(sys.argv[2], 0), int(sys.argv[3], 0) if len(sys.argv) > 3 else 256)))
    elif cmd == 'dword':
        fo = int(sys.argv[2], 0)
        print('0x%08x  (%d)' % (struct.unpack_from('<I', read(fo, 4))[0],
                                struct.unpack_from('<i', read(fo, 4))[0]))
    elif cmd == 'ptr':
        fo = int(sys.argv[2], 0)
        v = struct.unpack_from('<Q', read(fo, 8))[0]
        rva = v - IMG if v >= IMG else 0
        print('file 0x%X -> u64 0x%X  (VA 0x%X, rva 0x%X)' % (fo, v, v, rva))
        if rva:
            f2 = rva2file(rva)
            if f2 is not None:
                print('   target file 0x%X, first bytes: %s' %
                      (f2, ' '.join('%02x' % c for c in read(f2, 32))))
    elif cmd == 'findptr':
        va = int(sys.argv[2], 0)
        for fo, rva, sec in findptr(va):
            print('file 0x%X  rva 0x%X  [%s]' % (fo, rva or 0, sec or '?'))
    elif cmd == 'dis':
        va = int(sys.argv[2], 0)
        n = int(sys.argv[3], 0)
        import shutil
        import subprocess
        # Resolve llvm-objdump without hardcoding anyone's install path: prefer
        # the directory clang lives in (so it matches the toolchain build.bat
        # picked), then PATH, then let the OS resolve a bare name.
        objdump = None
        clang = shutil.which('clang')
        if clang:
            cand = os.path.join(os.path.dirname(clang), 'llvm-objdump.exe')
            if os.path.exists(cand):
                objdump = cand
        if not objdump:
            objdump = shutil.which('llvm-objdump') or 'llvm-objdump'
        r = subprocess.run([objdump, '-d', '--start-address=%d' % va,
                            '--stop-address=%d' % (va + n), EXE],
                           capture_output=True, text=True)
        print(r.stdout)
        if r.returncode:
            print(r.stderr)
    elif cmd == 'reflect':
        name = sys.argv[2]
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'kfc', 'reflection_data.json')
        with open(p, 'r', encoding='utf-8') as f:
            rd = json.load(f)
        hits = []
        def walk(o):
            if isinstance(o, dict):
                if o.get('qualifiedName') == name or o.get('name') == name:
                    hits.append(o)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        walk(rd)
        if not hits:
            # substring
            def walk2(o):
                if isinstance(o, dict):
                    qn = str(o.get('qualifiedName', '')) + str(o.get('name', ''))
                    if name.lower() in qn.lower():
                        hits.append(o)
                    for v in o.values():
                        walk2(v)
                elif isinstance(o, list):
                    for v in o:
                        walk2(v)
            walk2(rd)
        print('=== %d hit(s) for %r ===' % (len(hits), name))
        for h in hits[:5]:
            print(json.dumps(h, ensure_ascii=False, indent=1)[:8000])
    else:
        print(__doc__)

if __name__ == '__main__':
    main()
