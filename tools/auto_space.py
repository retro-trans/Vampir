"""Automatic per-message variants: a space after a pause (script opcode 1A nn), no extra
full stop after an ellipsis, a comma before the player name.

    python tools/auto_space.py [--dry]    -> work/translation/en/fixes/zz_auto_space.json

In Japanese a pause splits a sentence with no space; in English the fragment after the pause
needs one ("Stop it." <pause> " Whoa."). The variant is keyed at the message (or updates an
existing variant of that fragment inside the message).
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import talk  # noqa: E402

OUT = os.path.join(check.TR, 'fixes', 'zz_auto_space.json')
NO_SPACE_BEFORE = set('.,!?;:)]…\'"-~ ')


def vocabulary():
    words = set()
    for p in glob.glob(os.path.join(check.TR, 'done', '*.json')) + glob.glob(os.path.join(check.TR, 'fixes', '*.json')):
        if os.path.basename(p) == os.path.basename(OUT):
            continue
        for t in json.load(open(p, encoding='utf8')):
            for x in [t] + (t.get('variants') or []):
                words.update(w.lower() for w in re.findall(r'[A-Za-z]+', x.get('en') or ''))
    return words


VOCAB = set()


def fixes_for(ch):
    """Variants keyed at the string reference itself, so only that occurrence changes."""
    en, var = check.translations(ch, skip=os.path.basename(OUT))
    out = []

    def add(p, o, text, why):
        out.append({'file': '%s_C_%s.STC' % (ch, ch), 'id': '%s#%d' % (ch, p),
                    'variants': [{'ref': o, 'en': text}], 'why': 'auto: ' + why})

    for m in talk.messages(ch, len(en)):
        line, paused = '', False
        parts = m['parts']
        for i, p in enumerate(parts):
            if p == 'PAUSE':
                paused = True
                continue
            if isinstance(p, int):
                o = m['offs'][i]
                t = check.frag(m, i, en, var)[0]
                if t is None:
                    line, paused = '', False
                    continue
                if check.JP.get(p) != '\u30fb' and t.strip() == '.' and line.rstrip().endswith('...'):
                    add(p, o, '', 'full stop after an ellipsis')            # "..." + "\u3002" -> no 4th dot
                    paused = False
                    continue
                # a word split by the pause ("Stan" <p> "berg"): the joined form is a known word
                m1, m2 = re.search(r'[A-Za-z]+$', line), re.match(r'[A-Za-z]+', t)
                midword = bool(m1 and m2 and (m1.group() + m2.group()).lower() in VOCAB)
                if (paused and t and line and not line[-1].isspace() and t[:1] not in NO_SPACE_BEFORE
                        and not midword and line.strip('. ')):        # not after a line of dots only
                    t = ' ' + t
                    add(p, o, t, 'space after a pause')
                nxt = parts[i + 1] if i + 1 < len(parts) else None
                if nxt in ('NAME', 'PARTNER') and t and not t[-1].isspace() and not t.endswith('...'):
                    if t[-1].isalnum():
                        t2 = t + ', '                       # "Hm" + name -> "Hm, name"
                    elif t[-1] == '.':
                        t2 = t[:-1] + ', '                  # "Hello." + name -> "Hello, name"
                    elif t[-1] in '!?':
                        t2 = t + ' '
                    else:
                        t2 = t
                    if t2 != t:
                        if out and out[-1]['variants'][0]['ref'] == o:
                            out.pop()                       # replaces the pause-space variant
                        add(p, o, t2, 'separate the player name')
                        t = t2
                line += t
            elif p in ('NAME', 'PARTNER'):
                line += 'N'
            else:
                line = ''
            paused = False
    return out


def main():
    VOCAB.update(vocabulary())
    res = []
    for ch in ('M0', 'M1', 'M2'):
        if os.path.exists(os.path.join(check.TR, 'rows', '%s_C_%s.STC.json' % (ch, ch))):
            res += fixes_for(ch)
    for r in res:
        print(r['id'], r['variants'][0])
    if '--dry' not in sys.argv:
        json.dump(res, open(OUT, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print(len(res), 'variants', '(dry run)' if '--dry' in sys.argv else '')


if __name__ == '__main__':
    main()
