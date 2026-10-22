"""Check assembled villager messages (rows + done/ translations) for fit and joins.

    python tools/check.py M0 [--all]     -> report of problem messages
    python tools/check.py <slice>        -> only the messages that use the rows of that slice
Problems: a box (text up to a wait) needing more than 3 lines at 240 px, a fragment join
without a space between two words, doubled spaces, an untranslated fragment.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fit  # noqa: E402
import talk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')


def vkey(k, v):
    """Variant key: (row, message position) or (row, 'r<reference position>')."""
    return (k, 'r%d' % int(v['ref'])) if 'ref' in v else (k, int(v['msg']))


def translations(ch, skip=None):
    rows = json.load(open(os.path.join(TR, 'rows', '%s_C_%s.STC.json' % (ch, ch)), encoding='utf8'))
    en = {r['stc']: r.get('en') or None for r in rows if 'stc' in r}
    global JP
    JP = {r['stc']: r['jp'] for r in rows if 'stc' in r}
    var = {}                           # variants come from done/ and fixes/ only (rows hold applied copies)
    for p in glob.glob(os.path.join(TR, 'done', '%s_C_%s_STC_*.json' % (ch, ch))):
        for t in json.load(open(p, encoding='utf8')):
            if '#' in t['id']:
                k = int(t['id'].split('#')[1])
                en[k] = t.get('en')
                for v in t.get('variants') or []:
                    var[vkey(k, v)] = v['en']
    for p in sorted(glob.glob(os.path.join(TR, 'fixes', '*.json'))):
        if skip and os.path.basename(p) == skip:
            continue
        for t in json.load(open(p, encoding='utf8')):
            if t.get('file') == '%s_C_%s.STC' % (ch, ch) and '#' in t['id']:
                k = int(t['id'].split('#')[1])
                if 'en' in t:
                    en[k] = t['en']
                for v in t.get('variants') or []:
                    var[vkey(k, v)] = v['en']
    return en, var


def frag(m, i, en, var):
    """(text, key) of fragment i of message m: a variant keyed at this reference, else one keyed
    at the message (any position inside it that is not another reference), else the row."""
    p, o = m['parts'][i], m['offs'][i]
    if (p, 'r%d' % o) in var:
        return var[(p, 'r%d' % o)], (p, 'r%d' % o)
    for (k, at), t in var.items():
        if k == p and isinstance(at, int) and m['pos'] <= at < m['end']:
            return t, (k, at)
    return en.get(p), None


def boxes(m, en, var):
    """Split a message into boxes: list of lines (strings) per box; None if a fragment is missing."""
    out, lines, cur = [], [], ''
    missing = False
    for i, p in enumerate(m['parts']):
        if isinstance(p, int):
            t = frag(m, i, en, var)[0]
            if t is None:
                missing = True
                t = '<#%d>' % p
            cur += t
        elif p == 'NL':
            lines.append(cur)
            cur = ''
        elif p in ('NAME', 'PARTNER'):
            cur += '{PLAYER_NAME}'
        elif p in ('WAIT', 'CLEAR', 'PLAYER', 'VILLAGER'):
            if cur or lines:
                lines.append(cur)
                out.append(lines)
            lines, cur = [], ''
    if cur or lines:
        lines.append(cur)
        out.append(lines)
    for b in out:                      # a trailing empty line before the wait takes no space
        while len(b) > 1 and b[-1] == '':
            b.pop()
    return out, missing


def problems(ch, show_all=False, only=None):
    en, var = translations(ch)
    seen = set()
    res = []
    for m in talk.messages(ch, len(en)):
        if only is not None and not only.intersection(p for p in m['parts'] if isinstance(p, int)):
            continue
        bx, missing = boxes(m, en, var)
        key = json.dumps(bx)
        if key in seen:
            continue
        seen.add(key)
        if missing and not show_all:
            continue
        issues = []
        jb, _ = boxes(m, JP, {})
        for b, jl in zip(bx, jb):
            page = len(jl) > 3                     # Japanese box with > 3 lines: full-page text
            n = sum(fit.wrap(line, 264 if page else 240) for line in b)
            if n > (12 if page else 3):
                issues.append('%d lines%s' % (n, ' (page)' if page else ''))
            for line in b:
                if '  ' in line.strip():
                    issues.append('double space')
                if re.search(r'[a-z][A-Z]|[!?,][A-Za-z]|(?<![.])[.][A-Za-z]', line.replace('{PLAYER_NAME}', 'X')):
                    issues.append('join: %r' % line)
        if issues or (show_all and missing):
            res.append((m['pos'], m['villager'], issues, bx))
    return res


def bad_variants(ch):
    """Variants whose message does not contain their string (the build would fail)."""
    en, var = translations(ch)
    ms = talk.messages(ch, len(en))
    bad = []
    refs = {(p, 'r%d' % o) for m in ms for p, o in zip(m['parts'], m['offs']) if isinstance(p, int)}
    for (k, at) in var:
        if isinstance(at, str):
            if (k, at) not in refs:
                bad.append((k, at))
        elif not any(m['pos'] <= at < m['end'] and k in m['parts'] for m in ms):
            bad.append((k, at))
    return bad


if __name__ == '__main__':
    ch, only = sys.argv[1], None
    if len(ch) > 2:                      # a slice name: only messages that use its rows
        sl = json.load(open(os.path.join(TR, 'slices', ch + '.json'), encoding='utf8'))
        only = {int(r['id'].split('#')[1]) for r in sl['rows'] if '#' in r['id']}
        ch = ch[:2]
    for k, at in bad_variants(ch):
        print('BAD VARIANT: %s#%d keyed at %s, which does not contain it' % (ch, k, at))
    r = problems(ch, '--all' in sys.argv, only)
    for pos, v, issues, bx in r:
        print('msg %d (villager %d): %s' % (pos, v, '; '.join(issues)))
        for b in bx:
            print('    | ' + ' / '.join(b))
    print(len(r), 'messages with problems')

