"""Create / refresh the translation row files from the original disc.

    python tools/rows.py      -> work/translation/en/rows/<FILE>.json

Script overlays and the EXE: one row per referenced string (id FILE@offset), in script
order when the overlay has a string table (the table lists strings in script order).
STC: one row per villager line (id M0#k, in stored order), plus villager names / jobs.
Existing 'en' / 'note' fields are kept when the Japanese is unchanged.
Rows hold the Japanese ('jp'), so these files stay local (see .gitignore); tools/strip_jp.py
writes the committable *.en.json copies.
"""
import json
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extract_text  # noqa: E402
from stc import Stc  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'work', 'translation', 'en', 'rows')
KEEP = ('en', 'note', 'status')


def merge(path, rows):
    old = {}
    if os.path.exists(path):
        for r in json.load(open(path, encoding='utf8')):
            old[r['id']] = r
    for r in rows:
        o = old.get(r['id'])
        if o and o.get('jp') == r.get('jp'):
            for k in KEEP:
                if k in o:
                    r[k] = o[k]
        r.setdefault('en', '')
    json.dump(rows, open(path, 'w', encoding='utf8'), ensure_ascii=False, indent=1)


def table_order(strs, data, base):
    """Index of each string in the longest pointer table (script order), else None."""
    starts = {s['addr'] for s in strs}
    best = (0, 0)
    i = 0
    n = len(data) // 4
    while i < n:
        j = i
        while j < n and struct.unpack_from('<I', data, j * 4)[0] in starts:
            j += 1
        if j - i > best[1] - best[0]:
            best = (i, j)
        i = j + 1 if j == i else j
    order = {}
    for k in range(best[0], best[1]):
        a = struct.unpack_from('<I', data, k * 4)[0]
        order.setdefault(a, k - best[0])
    return order


_FONT = None


def font_chars():
    """Characters the game can draw: the union of the three chapter glyph tables."""
    global _FONT
    if _FONT is None:
        _FONT = set()
        for f in ['M0/C/M0.STC', 'M1/C/M1.STC', 'M2/C/M2.STC']:
            for g, c in Stc(os.path.join(extract_text.SRC, f)).table:
                try:
                    _FONT.add(c.decode('cp932'))
                except UnicodeDecodeError:
                    pass
    return _FONT


def displayable(t):
    """Real game text only: every double-byte character must exist in the game font."""
    return all(ord(c) < 0x80 or c in font_chars() for c in t)


# text whose glyphs are missing from the font tables but which the game does print
FORCE = {'MCX.BIN@228'}


def script_rows(fn):
    key0 = os.path.basename(fn)
    strs = [s for s in extract_text.extract(fn)
            if s['refs'] and (displayable(s['jp']) or '%s@%X' % (key0, s['off']) in FORCE)]
    e, data, base = extract_text.load(fn)
    order = table_order(strs, data, base)
    key = os.path.basename(fn)
    rows = []
    for s in sorted(strs, key=lambda s: (order.get(s['addr'], 10 ** 6), s['off'])):
        z = s['off'] + s['size']
        while z < len(data) and data[z] == 0:
            z += 1
        r = {'id': '%s@%X' % (key, s['off']), 'off': s['off'], 'size': s['size'],
             'slot': z - s['off'] - 1, 'refs': s['refs'], 'jp': s['jp']}
        if s['addr'] in order:
            r['idx'] = order[s['addr']]
        rows.append(r)
    return rows


def stc_rows(fn):
    s = Stc(os.path.join(extract_text.SRC, fn))
    key = os.path.basename(fn).split('.')[0]
    rows = []
    for i, v in enumerate(s.villagers):
        rows.append({'id': '%s/name%d' % (key, i), 'name': i, 'jp': v['name'].decode('cp932')})
        rows.append({'id': '%s/job%d' % (key, i), 'job': i, 'jp': v['job'].decode('cp932')})
    for k, t in enumerate(s.strings()):
        rows.append({'id': '%s#%d' % (key, k), 'stc': k, 'jp': t})
    return rows


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in extract_text.FILES:
        if fn.startswith('SLPS'):
            rows = script_rows(fn)
        else:
            rows = script_rows(fn)
        merge(os.path.join(OUT, fn.replace('/', '_') + '.json'), rows)
        print(fn, len(rows))
    for fn in ['M0/C/M0.STC', 'M1/C/M1.STC', 'M2/C/M2.STC']:
        rows = stc_rows(fn)
        merge(os.path.join(OUT, fn.replace('/', '_') + '.json'), rows)
        print(fn, len(rows))


if __name__ == '__main__':
    main()
