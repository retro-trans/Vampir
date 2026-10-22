"""Small MIPS (R3000) helpers for PS-X EXE reverse engineering.

    python tools/mips.py <exe> dis <addr> [count]     disassemble
    python tools/mips.py <exe> xref <addr>            find jal/j/address refs
    python tools/mips.py <exe> func <addr>            disassemble until jr ra (+delay)
"""
import struct
import sys

import capstone

SRC = 'work/source/disc/'


class Exe:
    def __init__(self, path, base=None):
        # 'FILE@base' or base=...: raw overlay loaded at base (e.g. DC/OPN.BIN@800CB800)
        if base is None and '@' in path:
            path, b = path.rsplit('@', 1)
            base = int(b, 16)
        self.data = open(path, 'rb').read()
        self.md = capstone.Cs(capstone.CS_ARCH_MIPS,
                              capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN)
        if base is not None:
            self.base = base
            self.body = self.data
            self.size = len(self.data)
            return
        self.base = struct.unpack_from('<I', self.data, 0x18)[0]
        self.size = struct.unpack_from('<I', self.data, 0x1C)[0]
        self.body = self.data[0x800:0x800 + self.size]
        self.md = capstone.Cs(capstone.CS_ARCH_MIPS,
                              capstone.CS_MODE_MIPS32 + capstone.CS_MODE_LITTLE_ENDIAN)

    def off(self, addr):
        return addr - self.base

    def word(self, addr):
        return struct.unpack_from('<I', self.body, self.off(addr))[0]

    def dis(self, addr, count=32):
        o = self.off(addr)
        out = []
        for i in range(count):
            w = self.body[o + i * 4:o + i * 4 + 4]
            ins = list(self.md.disasm(w, addr + i * 4))
            if ins:
                out.append((addr + i * 4, ins[0].mnemonic, ins[0].op_str))
            else:
                out.append((addr + i * 4, '.word', '0x%08x' % struct.unpack('<I', w)[0]))
        return out

    def func(self, addr, limit=2000):
        out = []
        for a, m, o in self.dis(addr, limit):
            out.append((a, m, o))
            if m == 'jr' and o == '$ra':
                out += self.dis(a + 4, 1)
                break
        return out

    def xref(self, target):
        hits = []
        jal = 0x0C000000 | ((target >> 2) & 0x3FFFFFF)
        j = 0x08000000 | ((target >> 2) & 0x3FFFFFF)
        hi = (target + 0x8000) >> 16
        lo = target & 0xFFFF
        n = len(self.body) // 4
        words = struct.unpack_from('<%dI' % n, self.body)
        for i, w in enumerate(words):
            a = self.base + i * 4
            if w == jal:
                hits.append((a, 'jal'))
            elif w == j:
                hits.append((a, 'j'))
            elif w == target:
                hits.append((a, 'ptr'))
            elif (w >> 16) & 0xFC1F == 0x2400 | 0 and False:
                pass
            elif (w & 0xFFFF) == lo and (w >> 26) in (0x09, 0x23, 0x2B, 0x21, 0x25, 0x29, 0x20, 0x28):
                # addiu/lw/sw/... with matching low half: check a preceding lui
                rs = (w >> 21) & 31
                for k in range(1, 12):
                    if i - k < 0:
                        break
                    pw = words[i - k]
                    if pw >> 26 == 0x0F and (pw >> 16) & 31 == rs and pw & 0xFFFF == hi & 0xFFFF:
                        hits.append((a, 'lui/lo'))
                        break
        return hits


def fmt(rows):
    return '\n'.join('%08X  %-7s %s' % r for r in rows)


def main():
    exe = sys.argv[1]
    import os
    if not os.path.exists(exe.split('@')[0]):
        exe = SRC + exe
    e = Exe(exe)
    cmd = sys.argv[2]
    addr = int(sys.argv[3], 16)
    if cmd == 'dis':
        print(fmt(e.dis(addr, int(sys.argv[4]) if len(sys.argv) > 4 else 32)))
    elif cmd == 'func':
        print(fmt(e.func(addr)))
    elif cmd == 'xref':
        for a, k in e.xref(addr):
            print('%08X %s' % (a, k))


if __name__ == '__main__':
    main()
