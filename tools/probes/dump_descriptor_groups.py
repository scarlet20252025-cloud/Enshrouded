r"""Decode the enemy_transformer descriptor's component-name groups correctly.

wildlife_enemy_transformer descriptor @ rva 0x1e2b860:
  +0x00 char* name      (0x141e2bbe8, 'wildlife_enemy_transformer', len 0x1a)
  +0x08 u64   nameLen
  +0x10 void* handler   (0x140480c70)
  +0x18..0x40  ZERO     (3 zero pairs = 3 empty groups!)
  +0x48 {ptr=0x141e2b808, count=1}
  +0x58 {ptr=0x141e2b818, count=3}
  +0x68 0 (terminator)

The generic loop broke on the first zero pair. Fix: iterate a FIXED number of
slots read from... we don't know the count. Instead: iterate pairs until we have
consumed the whole descriptor region, treating {0,0} as an EMPTY group (valid),
and stop at the first pair whose ptr is 0 AND count is 0 AND everything after is 0.
Simplest robust rule: walk pairs while (ptr != 0 || count != 0) OR we have seen
fewer than K pairs... Use: stop when ptr==0 && count==0 && next pair also ==0.
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import scanrefs as S  # noqa: E402

EXE = r"E:\SteamLibrary\steamapps\common\Enshrouded\enshrouded.exe"
IB = S.IMAGE_BASE
TARGETS = [0x1E2B860, 0x1E2BA50]


def rva2off(secs, rva):
    for s in secs:
        if s["va"] <= rva < s["va"] + max(s["vsize"], s["rawsize"]):
            return s["raw"] + (rva - s["va"])
    return None


def cstr(data, secs, va):
    off = rva2off(secs, va - IB)
    if off is None:
        return None
    end = data.find(b"\0", off)
    if end < 0 or end - off > 200:
        return None
    try:
        return data[off:end].decode("utf-8")
    except UnicodeDecodeError:
        return None


def names_at(data, secs, ptr, cnt):
    off = rva2off(secs, ptr - IB)
    if off is None or cnt > 32:
        return None
    out = []
    for j in range(cnt):
        np_ = struct.unpack_from("<Q", data, off + j * 16)[0]
        s = cstr(data, secs, np_)
        if s is None:
            return None
        out.append(s)
    return out


def main():
    data = open(EXE, "rb").read()
    secs = S.sections(data)
    for rva in TARGETS:
        off = rva2off(secs, rva)
        namep, namelen, handler = struct.unpack_from("<QQQ", data, off)
        print("=" * 74)
        print("%r  (len %d)  handler rva=%#x" % (cstr(data, secs, namep), namelen, handler - IB))
        p = off + 0x18
        for k in range(8):
            ptr, cnt = struct.unpack_from("<QI", data, p)
            if ptr == 0 and cnt == 0:
                # could be an empty group; peek two slots ahead
                nxt = struct.unpack_from("<QI", data, p + 16)
                if nxt == (0, 0):
                    break
                print("   group %d: EMPTY" % k)
                p += 16
                continue
            ns = names_at(data, secs, ptr, cnt)
            print("   group %d rva=%#x n=%d: %s" % (k, ptr - IB, cnt,
                  ", ".join(ns) if ns else "<bad>"))
            p += 16


if __name__ == "__main__":
    main()
