"""Dump the VWF quad buffer of the running game: python tools/quads.py [n]"""
import os
import struct
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 12
g = Gdb()
cnt = struct.unpack('<H', g.read(0x800af62a, 2))[0]
fr = struct.unpack('<h', g.read(0x800c54cc, 2))[0]
print('count', cnt, 'frame', fr)


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


for f in (0, 1):
    d = g.read(0x800AC790 + f * 4800, 40 * n)
    for i in range(n):
        q = struct.unpack_from('<10I', d, i * 40)
        print(f, i, '%08x' % q[0], 'x %d..%d y %d..%d' % (s16(q[2]), s16(q[4]), s16(q[2] >> 16), s16(q[6] >> 16)),
              'uv %04x %04x clut %04x tp %04x' % (q[3] & 0xFFFF, q[9] & 0xFFFF, q[3] >> 16, q[5] >> 16))
g.close()
