"""Assemble story script boxes (overlays) from their bytecode and check the English.

    python tools/story_check.py [FILE ...]      (default: every overlay with a rows file)

Script bytes: 0D hh ll string (table index), 0E hh ll aa string with attribute, 0F newline,
10 wait, 0C clear, 18 player name, 19 partner name, 11/12 speaker, 1A nn pause, 0B nn
attribute.  Lines are measured with tools/fit.py (names as 8 letters) against 240 px; joins
without a space are flagged as in tools/check.py.  Reports lines that would wrap.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')
SRC = os.path.join(ROOT, 'work', 'source', 'disc')
IGNORE = {('M2_C_M2A.BIN', 0xE1EE)}   # runs that are event tables, not dialogue
ONE = {0x0F: 'NL', 0x10: 'WAIT', 0x0C: 'CLEAR', 0x18: 'NAME', 0x19: 'PARTNER',
       0x11: 'PLAYER', 0x12: 'VILLAGER'}


def overlay_texts(name):
    """{table index: (row id, english)} and the overlay bytes."""
    rows = json.load(open(os.path.join(TR, 'rows', name.replace('/', '_') + '.json'), encoding='utf8'))
    fixes = {}
    for p in sorted(glob.glob(os.path.join(TR, 'fixes', '*.json'))):
        for t in json.load(open(p, encoding='utf8')):
            if 'en' in t:
                fixes[t['id']] = t['en']
    by_idx = {r['idx']: (r['id'], fixes.get(r['id'], r.get('en'))) for r in rows if 'idx' in r}
    global JP
    JP = {r['idx']: r['jp'] for r in rows if 'idx' in r}
    file = name.split('_', 1)[0] + '/' + name.split('_', 1)[1] if '/' not in name else name
    return by_idx, file


def runs(data, n):
    i = 0
    while i < len(data):
        parts, j = [], i
        while j < len(data):
            b = data[j]
            if b == 0x0D and j + 2 < len(data) and (data[j + 1] << 8 | data[j + 2]) < n:
                parts.append(data[j + 1] << 8 | data[j + 2])
                j += 3
            elif b == 0x0E and j + 3 < len(data) and (data[j + 1] << 8 | data[j + 2]) < n:
                parts.append(data[j + 1] << 8 | data[j + 2])
                j += 4
            elif b == 0x1A and parts and j + 1 < len(data) and data[j + 1] <= 60:
                j += 2
            elif b == 0x0B and parts and j + 1 < len(data):
                j += 2
            elif b in ONE and (parts or b in (0x0C, 0x0F, 0x10, 0x11, 0x12)):
                parts.append(ONE[b])
                j += 1
            else:
                break
        if any(isinstance(p, int) for p in parts) and any(p in ('NL', 'WAIT', 'CLEAR') for p in parts):
            yield i, parts
            i = j
        else:
            i = max(j, i + 1)


def check(rows_name):
    by_idx, _ = overlay_texts(rows_name)
    fn = rows_name.replace('DC_', 'DC/').replace('_C_', '/C/')
    data = open(os.path.join(SRC, fn), 'rb').read()
    n = max(by_idx) + 1 if by_idx else 0
    out = []
    for pos, parts in runs(data, n):
        if (rows_name, pos) in IGNORE:
            continue
        boxes, lines, cur, ids = [], [], '', []
        jl, jmax, jmaxes = 0, 0, []
        for p in parts + ['WAIT']:
            if isinstance(p, int):
                rid, t = by_idx.get(p, ('?', None))
                ids.append(rid)
                cur += t if t is not None else '<%s>' % rid
                jl += len(JP.get(p, ''))
            elif p == 'NL':
                lines.append(cur)
                cur = ''
                jmax, jl = max(jmax, jl), 0
            elif p in ('NAME', 'PARTNER'):
                cur += '{PLAYER_NAME}'
            elif p in ('WAIT', 'CLEAR', 'PLAYER', 'VILLAGER'):
                if cur or lines:
                    lines.append(cur)
                    boxes.append(lines)
                    jmaxes.append(max(jmax, jl))
                lines, cur, jl, jmax = [], '', 0, 0
        for b, jm in zip(boxes, jmaxes):
            flat = ''.join(b).replace('{PLAYER_NAME}', 'X')
            if len(flat) > 40 and any(flat == flat[:k] * (len(flat) // k) for k in range(8, 41)):
                continue                           # one sentence repeated across the screen (effect)
            while len(b) > 1 and b[-1] == '':
                b.pop()
            page = len(b) > 3 or jm > 20           # full-page text (diary pages): 264 px, 12 lines
            w = 264 if page else 240
            issues = []
            for line in b:
                t = line.replace('{PLAYER_NAME}', 'X')
                if len(t) > 40 and t[:len(t) // 2] * 2 == t:
                    continue                       # a sentence repeated across the screen (effect)

                if re.search(r'[a-z][A-Z]|[!?,][A-Za-z]|(?<![.])[.][A-Za-z]', line.replace('{PLAYER_NAME}', 'X')):
                    issues.append('join')
                if '  ' in line.strip():
                    issues.append('double space')
            nl = sum(fit.wrap(line, w) for line in b)
            if nl > (12 if page else 3):
                issues.append('%d lines%s' % (nl, ' (page)' if page else ''))
            if issues:
                out.append((pos, sorted(set(issues)), b, ids))
    return out


def main():
    names = sys.argv[1:] or sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(TR, 'rows', '*.BIN.json')))
    total = 0
    for nm in names:
        if 'SLPS' in nm:
            continue
        res = check(nm)
        total += len(res)
        for pos, issues, b, ids in res:
            print('%s @%X: %s' % (nm, pos, ', '.join(issues)))
            for line in b:
                print('    | ' + line)
    print(total, 'boxes with problems')


if __name__ == '__main__':
    main()
