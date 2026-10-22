"""Cut the translation rows into 80-row slices with context for translation agents.

    python tools/slices.py make          -> work/translation/en/slices/<name>.json (+ index.json)
    python tools/slices.py status        -> slices done / pending
    python tools/slices.py apply         -> merge work/translation/en/done/<name>.json into the rows

A slice file lists its rows (id, jp, and for villager text the messages that use the
row, rendered with fragment ids, speaker and villager), plus 10 rows of context on
each side. Agents write done/<name>.json: [{"id", "en", "note"?, "variants"?}].
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import talk  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')
ROWS = os.path.join(TR, 'rows')
SLICES = os.path.join(TR, 'slices')
DONE = os.path.join(TR, 'done')
SIZE = 80
ORDER = ['DC_OPN.BIN', 'M0_C_M0.STC', 'M0_C_PR0.BIN', 'M0_C_M0A.BIN', 'M0_C_EP0.BIN',
         'M1_C_PR1.BIN', 'M1_C_M1.STC', 'M1_C_M1A.BIN', 'M1_C_EP1.BIN',
         'M2_C_PR2.BIN', 'M2_C_M2.STC', 'M2_C_M2A.BIN', 'M2_C_EP2.BIN',
         'DC_END.BIN', 'DC_MCX.BIN', 'SLPS_019.32']


def glossary():
    return json.load(open(os.path.join(ROOT, 'work', 'glossary', 'glossary.json'), encoding='utf8'))


def villager_info(ch):
    g = glossary()
    return {v['index']: v for v in g['villagers'] if v['chapter'] == ch}


def stc_context(ch, rows):
    """Messages per STC index: rendered with «#k text» fragments."""
    text = {r['stc']: r['jp'] for r in rows if 'stc' in r}
    vinfo = villager_info(ch)
    uses = {}
    for m in talk.messages(ch, len(text)):
        v = vinfo.get(m['villager'], {})
        who = '%s (%s, %s, age %s)' % (v.get('en'), v.get('gender'), v.get('job_jp'), v.get('age'))
        out, speaker = [], None
        for p in m['parts']:
            if isinstance(p, int):
                out.append('«#%d %s»' % (p, text[p]))
            elif p == 'NL':
                out.append(' / ')
            elif p == 'NAME':
                out.append('{PLAYER_NAME}')
            elif p == 'PARTNER':
                out.append('{PARTNER_NAME}')
            elif p == 'PLAYER':
                out.append('\n[PLAYER] ')
            elif p == 'VILLAGER':
                out.append('\n[%s] ' % (v.get('en') or 'VILLAGER'))
            elif p == 'WAIT':
                out.append(' ▼')
            elif p == 'CLEAR':
                pass
        s = ''.join(out).strip()
        for p in m['parts']:
            if isinstance(p, int):
                lst = uses.setdefault(p, [])
                if len(lst) < 6 and all(u['text'] != s for u in lst):
                    lst.append({'msg': m['pos'], 'villager': who, 'text': s})
    return uses


def make():
    os.makedirs(SLICES, exist_ok=True)
    index = []
    for name in ORDER:
        p = os.path.join(ROWS, name + '.json')
        rows = json.load(open(p, encoding='utf8'))
        ctx = {}
        if name.endswith('.STC'):
            ch = name[:2]
            ctx = stc_context(ch, rows)
            text_rows = [r for r in rows if 'stc' in r]
            label_rows = [r for r in rows if 'stc' not in r]
        else:
            text_rows, label_rows = rows, []
        groups = []
        if label_rows:
            groups.append(('labels', label_rows))
        for k in range(0, len(text_rows), SIZE):
            groups.append(('%03d' % (k // SIZE), text_rows[k:k + SIZE]))
        for tag, grp in groups:
            sname = '%s_%s' % (name.replace('.', '_'), tag)
            allr = label_rows if tag == 'labels' else text_rows
            i0 = allr.index(grp[0])
            before = [{'id': r['id'], 'jp': r['jp']} for r in allr[max(0, i0 - 10):i0]]
            after = [{'id': r['id'], 'jp': r['jp']} for r in allr[i0 + len(grp):i0 + len(grp) + 10]]
            items = []
            for r in grp:
                it = {'id': r['id'], 'jp': r['jp']}
                if 'stc' in r and r['stc'] in ctx:
                    it['used_in'] = ctx[r['stc']]
                if r.get('en'):
                    it['current_en'] = r['en']
                items.append(it)
            json.dump({'slice': sname, 'file': name, 'rows': items, 'before': before, 'after': after},
                      open(os.path.join(SLICES, sname + '.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=1)
            index.append({'slice': sname, 'file': name, 'rows': len(grp)})
    json.dump(index, open(os.path.join(SLICES, 'index.json'), 'w', encoding='utf8'), indent=0)
    print(len(index), 'slices,', sum(i['rows'] for i in index), 'rows')


def status():
    index = json.load(open(os.path.join(SLICES, 'index.json')))
    done = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DONE, '*.json'))}
    n = sum(1 for i in index if i['slice'] in done)
    print('%d / %d slices done' % (n, len(index)))
    return index, done


def apply():
    index = json.load(open(os.path.join(SLICES, 'index.json')))
    by_file = {}
    for i in index:
        p = os.path.join(DONE, i['slice'] + '.json')
        if os.path.exists(p):
            by_file.setdefault(i['file'], []).append(p)
    # proofreading fixes (fixes/<name>.json: [{"file": rows name, "id", "en", "variants"?}]) after the slices
    fixes = []
    for p in sorted(glob.glob(os.path.join(TR, 'fixes', '*.json'))):
        fixes += json.load(open(p, encoding='utf8'))
    for f in fixes:
        by_file.setdefault(f['file'], [])
    total = 0
    for name, paths in by_file.items():
        rp = os.path.join(ROWS, name + '.json')
        rows = json.load(open(rp, encoding='utf8'))
        by_id = {r['id']: r for r in rows}
        for r in rows:                          # variants are rebuilt from done/ and fixes/
            r.pop('variants', None)
        for p in paths:
            for t in json.load(open(p, encoding='utf8')):
                r = by_id.get(t['id'])
                if r is None:
                    print('unknown id', t['id'], 'in', p)
                    continue
                r['en'] = t.get('en', '')
                r['done'] = True                    # translated (an empty "en" is a real translation)
                for k in ('note', 'variants'):
                    if t.get(k):
                        r[k] = t[k]
                total += 1
        for t in fixes:
            if t['file'] == name and t['id'] in by_id:
                r = by_id[t['id']]
                if 'en' in t:
                    r['en'] = t['en']
                    r['done'] = True
                if 'variants' in t:                 # merge by message (a fix replaces the same msg)
                    key = lambda v: ('ref', int(v['ref'])) if 'ref' in v else ('msg', int(v['msg']))
                    vs = {key(v): v for v in r.get('variants') or []}
                    vs.update({key(v): v for v in t['variants']})
                    r['variants'] = list(vs.values())
                total += 1
        json.dump(rows, open(rp, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('applied', total, 'rows')


if __name__ == '__main__':
    {'make': make, 'status': status, 'apply': apply}[sys.argv[1]]()
