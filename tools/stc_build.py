"""Rebuild an M?.STC file with English text (see tools/stc.py for the format).

    data = build(orig_bytes, dictionary, strings_en, names_en, jobs_en)

* villager records keep their ids and stats; name/job become 2-byte token codes
  (runtime-encoded by the game, up to 11 tokens + NUL in the 24-byte fields);
* the table lists every token, ordered by this chapter's frequencies, with nibble
  parameters chosen for the smallest text;
* string k keeps index k (the game addresses villager lines by index); strings are
  stored back to back without suffix sharing.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vtext  # noqa: E402
from stc import Stc  # noqa: E402

LIMIT = 0x34000          # 0x800EE800 + LIMIT = 0x80122800, the next fixed load (M?.VCT)


def field(d, text, size=24):
    b = d.sjis(d.tokenize(text)) if text else b''
    if len(b) > size - 2:
        raise ValueError('%r does not fit a %d-byte field (%d)' % (text, size, len(b)))
    return b.ljust(size, b'\0')


def build(orig, d, strings, names, jobs):
    s = Stc.__new__(Stc)
    s.d = orig
    s.rec_off, s.tab_off, s.txt_off, s.nvill = struct.unpack_from('<4I', orig, 0)
    n_str = struct.unpack_from('<I', orig, s.txt_off)[0] // 8
    if len(strings) < n_str:
        raise ValueError('need %d strings, got %d' % (n_str, len(strings)))
    n_str = len(strings)                  # variants append strings after the original ones
    # records
    rec = bytearray(orig[s.rec_off:s.tab_off])
    nrec = struct.unpack_from('<I', rec, 0)[0]
    for i in range(nrec):
        r = 4 + i * 0x44
        rec[r + 2:r + 0x1a] = field(d, names[i])
        rec[r + 0x1a:r + 0x32] = field(d, jobs[i])
    ids = [d.tokenize(t) for t in strings]
    tab = vtext.Table(d, ids)
    table = tab.header_and_entries()
    # text: offsets then nibble strings
    nibs = []
    starts = []
    for k, t in enumerate(ids):
        starts.append(len(nibs))
        nibs += tab.nibbles(t)
    head = 8 * n_str                      # nibbles taken by the offset table
    offs = b''.join(struct.pack('<I', head + st - 8 * k) for k, st in enumerate(starts))
    if len(nibs) % 2:
        nibs.append(0)
    body = bytes((nibs[i] << 4) | nibs[i + 1] for i in range(0, len(nibs), 2))
    tab_off = s.rec_off + len(rec)
    txt_off = tab_off + len(table)
    out = struct.pack('<3I', s.rec_off, tab_off, txt_off) + bytes(rec) + table + offs + body
    if len(out) > LIMIT:
        raise ValueError('STC too large: 0x%X > 0x%X' % (len(out), LIMIT))
    return out, tab


def verify(data, d, strings):
    """Decode the rebuilt file with the game's algorithm and compare."""
    s = Stc.__new__(Stc)
    s.d = data
    s.rec_off, s.tab_off, s.txt_off = struct.unpack_from('<3I', data, 0)
    s.P = list(data[s.tab_off:s.tab_off + 4])
    s.table = []
    o = s.tab_off + 4
    while o + 4 <= s.txt_off:
        s.table.append((struct.unpack_from('<H', data, o)[0], data[o + 2:o + 4]))
        o += 4
    for k, t in enumerate(strings):
        got = ''.join(d.tokens[s.table[i][0]] for i in s.codes(k))
        if got != vtext.normalize(t):
            raise AssertionError('string %d: %r != %r' % (k, got, t))
    return True
