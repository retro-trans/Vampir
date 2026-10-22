"""Extract Japanese strings from the EXE and overlays with every reference to them.

    python tools/extract_text.py            -> work/source/text/<file>.json (Japanese, git-ignored)

A string is a NUL-terminated run of Shift-JIS/ASCII bytes containing at least one
double-byte character. References: aligned 32-bit words equal to the string's RAM
address ('ptr', data tables) and lui + addiu/ori pairs ('code').
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from absrefs import refs as code_refs  # noqa: E402
from mips import Exe  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc')
OUT = os.path.join(ROOT, 'work', 'source', 'text')
OVL = 0x800CB800
FILES = ['SLPS_019.32', 'DC/OPN.BIN', 'DC/MCX.BIN', 'DC/END.BIN',
         'M0/C/M0A.BIN', 'M0/C/EP0.BIN', 'M0/C/PR0.BIN',
         'M1/C/M1A.BIN', 'M1/C/EP1.BIN', 'M1/C/PR1.BIN',
         'M2/C/M2A.BIN', 'M2/C/EP2.BIN', 'M2/C/PR2.BIN']
RUN = re.compile(rb'(?:[\x81-\x9f\xe0-\xef][\x40-\xfc]|[\x20-\x7e])+\x00')


def load(fn):
    p = os.path.join(SRC, fn)
    if fn.startswith('SLPS'):
        e = Exe(p)
        return e, e.body, e.base
    e = Exe(p, OVL)
    return e, e.body, OVL


def extract(fn):
    e, d, base = load(fn)
    strs = []
    for m in RUN.finditer(d):
        raw = m.group()[:-1]
        try:
            t = raw.decode('cp932')
        except UnicodeDecodeError:
            continue
        if not any(ord(c) > 0x7F for c in t):
            continue
        strs.append({'off': m.start(), 'addr': base + m.start(), 'jp': t, 'size': len(raw)})
    n = len(d) // 4
    w = struct.unpack_from('<%dI' % n, d)
    # pointers into the middle of a run (e.g. '--' + text, pointer at the text)
    spans = sorted((s['addr'], s['addr'] + s['size'], s) for s in strs)
    import bisect
    starts = [a for a, _, _ in spans]
    extra = []
    for x in set(w):
        k = bisect.bisect_right(starts, x) - 1
        if k >= 0:
            a, end, s0 = spans[k]
            if a < x < end:
                raw = d[x - base:end - base]
                try:
                    t = raw.decode('cp932')
                except UnicodeDecodeError:
                    continue
                if any(ord(c) > 0x7F for c in t):
                    extra.append({'off': x - base, 'addr': x, 'jp': t, 'size': len(raw)})
    strs += extra
    by = {s['addr']: s for s in strs}
    for s in strs:
        s['refs'] = []
    for i, x in enumerate(w):
        if x in by:
            by[x]['refs'].append(['ptr', base + i * 4])
    for a, at in code_refs(e):
        if a in by:
            by[a]['refs'].append(['code', at])
    return strs


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in FILES:
        strs = extract(fn)
        noref = sum(1 for s in strs if not s['refs'])
        name = fn.replace('/', '_')
        json.dump(strs, open(os.path.join(OUT, name + '.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
        print('%-16s %4d strings %6d chars  unreferenced %d' % (fn, len(strs), sum(len(s['jp']) for s in strs), noref))


if __name__ == '__main__':
    main()
