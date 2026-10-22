"""Operand byte counts of the script interpreter's opcodes (EXE 0x8004C730, table 0x80010FAC).

Static scan of each handler: follows the script pointer (0x1E8(s1)) through lw / addiu /
sw and records the last stored offset before the handler jumps back to the dispatcher.

    python tools/opcodes.py        -> prints {opcode: operand bytes}
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mips import Exe  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLE = 0x80010FAC
DEFAULT = 0x8004DA30
NEXT = (0x8004DA48,)


def handler_len(e, a, limit=200):
    regs = {}                 # reg -> offset from the operand start
    stored = None
    for _ in range(limit):
        w = e.word(a)
        op = w >> 26
        rs, rt, rd = (w >> 21) & 31, (w >> 16) & 31, (w >> 11) & 31
        imm = w & 0xFFFF
        simm = imm - 0x10000 if imm & 0x8000 else imm
        if op == 0x23 and rs == 17 and imm == 0x1E8:          # lw R, 0x1e8(s1)
            regs[rt] = 0
        elif op == 0x2B and rs == 17 and imm == 0x1E8:        # sw R, 0x1e8(s1)
            if rt in regs:
                stored = regs[rt]
        elif op == 0x09 and rs in regs:                       # addiu
            regs[rt] = regs[rs] + simm
        elif op == 0 and (w & 0x3F) == 0x21 and rs in regs and rt == 0:
            regs[rd] = regs[rs]
        elif op in (0x09, 0x0F, 0x0D, 0x23, 0x24, 0x20, 0x21, 0x25) and rt in regs:
            regs.pop(rt, None)
        if op == 0x02:                                        # j
            t = (a & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            a += 4
            w2 = e.word(a)
            if w2 >> 26 == 0x2B and (w2 >> 21) & 31 == 17 and (w2 & 0xFFFF) == 0x1E8 and ((w2 >> 16) & 31) in regs:
                stored = regs[(w2 >> 16) & 31]
            if t in NEXT or t == DEFAULT:
                return stored
            a = t
            continue
        if op == 0 and (w & 0x3F) == 0x08:                    # jr
            return stored
        a += 4
    return stored


def table():
    e = Exe(os.path.join(ROOT, 'work', 'source', 'disc', 'SLPS_019.32'))
    tab = struct.unpack_from('<245I', e.body, TABLE - e.base)
    out = {}
    for i, h in enumerate(tab):
        if h == DEFAULT:
            continue
        out[i] = handler_len(e, h)
    return out


if __name__ == '__main__':
    for k, v in sorted(table().items()):
        print('%02X:%s' % (k, v), end='  ')
    print()
