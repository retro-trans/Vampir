"""Run the game with read/write watchpoints while pressing pad buttons; log the hits.

    python tools/gdbwatch.py <r|w|a> <addr> <len> [--press circle --every 30 --frames 600 --max 40]
Watch length ≤ 0x100 per watchpoint (several are set to cover longer ranges).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gdbdbg  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('kind')
ap.add_argument('addr')
ap.add_argument('length')
ap.add_argument('--press', default='circle')
ap.add_argument('--every', type=int, default=40)
ap.add_argument('--frames', type=int, default=600)
ap.add_argument('--max', type=int, default=40)
a = ap.parse_args()
z = {'w': '2', 'r': '3', 'a': '4'}[a.kind]
addr, ln = int(a.addr, 16), int(a.length, 16)
d = gdbdbg.Dbg()
g = d.g
ws = [(x, min(0x100, addr + ln - x)) for x in range(addr, addr + ln, 0x100)]
for x, n in ws:
    assert g.cmd('Z%s,%x,%x' % (z, x, n)) == 'OK'
frame = 0
hits = 0
seen = {}
try:
    while frame < a.frames and hits < a.max:
        g.s.sendall(b'$c#63')
        g._recv_packet()
        r = d.regs()
        if r[37] == d.bp:
            if (r[7] & 0xFFFF) == 0:
                frame += 1
                if a.press and frame % a.every < 3:
                    d.setreg(2, r[2] | gdbdbg.BTN[a.press])
            continue
        hits += 1
        k = (r[37], r[31])
        seen[k] = seen.get(k, 0) + 1
        if seen[k] <= 2:
            print('pc %08x ra %08x a0 %08x a1 %08x a2 %08x a3 %08x v0 %08x v1 %08x s0 %08x s1 %08x frame %d' % (
                r[37], r[31], r[4], r[5], r[6], r[7], r[2], r[3], r[16], r[17], frame), flush=True)
finally:
    for x, n in ws:
        g.cmd('z%s,%x,%x' % (z, x, n))
    d.close()
print('frames', frame, 'hits', hits)
