"""List absolute addresses formed by lui+addiu/ori/load/store pairs in an EXE or overlay.

    python tools/absrefs.py <file[@base]> <lo> <hi>    -> address  [code locations]
"""
import struct
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mips import Exe, SRC  # noqa: E402


def refs(e):
    n = len(e.body) // 4
    w = struct.unpack_from('<%dI' % n, e.body)
    out = []
    for i in range(n):
        x = w[i]
        if x >> 26 != 0x0F:
            continue
        rt = (x >> 16) & 31
        hi = x & 0xFFFF
        for k in range(1, 24):
            if i + k >= n:
                break
            y = w[i + k]
            op = y >> 26
            rs = (y >> 21) & 31
            if rs == rt and op in (0x09, 0x0D, 0x20, 0x21, 0x23, 0x24, 0x25, 0x28, 0x29, 0x2B, 0x22, 0x26, 0x2A, 0x2E):
                lo = y & 0xFFFF
                if op == 0x0D:
                    a = (hi << 16) | lo
                else:
                    a = ((hi << 16) + (lo - 0x10000 if lo & 0x8000 else lo)) & 0xFFFFFFFF
                out.append((a, e.base + (i + k) * 4))
            # stop if rt overwritten
            if op in (0x0F, 0x09, 0x0D) and ((y >> 16) & 31) == rt and not (op != 0x0F and rs == rt):
                break
    return out


if __name__ == '__main__':
    f = sys.argv[1]
    if not os.path.exists(f.split('@')[0]):
        f = SRC + f
    e = Exe(f)
    lo, hi = int(sys.argv[2], 16), int(sys.argv[3], 16)
    d = {}
    for a, at in refs(e):
        if lo <= a < hi:
            d.setdefault(a, []).append(at)
    for a in sorted(d):
        print('%08X  %s' % (a, ' '.join('%08X' % x for x in d[a][:6])))
