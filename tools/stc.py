"""Parse the per-chapter M?.STC files: villager records, glyph/frequency table, nibble-coded text.

Layout (12-byte header [0x0C, tab_off, txt_off]):
  0x0C   u32 n, then n records of 0x44 bytes: u16 ?, name[24] SJIS, job[24] SJIS, 18 bytes stats
  tab    u8 P0 P1 P2 ?, then entries {u16 glyph, u8[2] sjis} (frequency order) up to txt
  txt    u32 nibble offsets, self-relative (string k starts at nibble 8k + off[k] from txt),
         then the strings back to back, each ending with the TERM code

Nibble code (EXE 0x800457EC): read up to four nibbles (high nibble first in each byte);
nibble k < P[k] continues the code (k < 3).  The terminator index is TERM; table
index = code index (+1 when >= TERM).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc')


class Stc:
    def __init__(self, path):
        self.d = d = open(path, 'rb').read()
        h = struct.unpack_from('<4I', d, 0)
        self.rec_off, self.tab_off, self.txt_off, self.nvill = h
        self.P = list(d[self.tab_off:self.tab_off + 4])
        self.table = []
        o = self.tab_off + 4
        while o + 4 <= self.txt_off:
            g, = struct.unpack_from('<H', d, o)
            self.table.append((g, d[o + 2:o + 4]))
            o += 4
        self.villagers = []
        n, = struct.unpack_from('<I', d, self.rec_off)
        for i in range(n):
            r = self.rec_off + 4 + i * 0x44
            self.villagers.append({'id': struct.unpack_from('<H', d, r)[0],
                                   'name': d[r + 2:r + 0x1a].split(b'\0')[0],
                                   'job': d[r + 0x1a:r + 0x32].split(b'\0')[0],
                                   'stats': d[r + 0x32:r + 0x44]})

    @property
    def term(self):
        return 16 - self.P[0]          # EXE 0x80045DAC

    def count(self):
        return struct.unpack_from('<I', self.d, self.txt_off)[0] // 8

    def start(self, k):
        return 8 * k + struct.unpack_from('<I', self.d, self.txt_off + 4 * k)[0]

    def codes(self, k):
        it = self.nibbles(self.start(k))
        out = []
        while True:
            i, _ = self.decode_code(it)
            if i == self.term:
                return out
            out.append(i - 1 if i > self.term else i)

    def text(self, k):
        return b''.join(self.table[i][1] for i in self.codes(k)).decode('cp932')

    def strings(self):
        return [self.text(k) for k in range(self.count())]

    def nibbles(self, pos):
        d = self.d
        while True:
            b = d[self.txt_off + pos // 2]
            yield (b >> 4) if pos % 2 == 0 else (b & 15)
            pos += 1

    def decode_code(self, it):
        P0, P1, P2 = self.P[0], self.P[1], self.P[2]
        n = [next(it)]
        if n[0] >= P0:
            return n[0] - P0, 1
        n.append(next(it))
        if n[1] >= P1:
            return n[0] * (16 - P1) + n[1] - P1 + 16 - P0, 2
        n.append(next(it))
        if n[2] >= P2:
            return (n[0] * P1 + n[1]) * (16 - P2) + n[2] - P2 + (16 - P0) + P0 * (16 - P1), 3
        n.append(next(it))
        return ((((n[0] * P1 + n[1]) * P2 + n[2]) * 16 + n[3]) + (16 - P0) + P0 * (16 - P1)
                + P0 * P1 * (16 - P2)), 4


if __name__ == '__main__':
    s = Stc(os.path.join(SRC, sys.argv[1]))
    print('P', s.P, 'table', len(s.table), 'villagers', len(s.villagers))
