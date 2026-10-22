"""Write Japanese-free copies of translation working files for git (AGENTS.md rule).

    python tools/strip_jp.py            -> <file>.en.json next to every working file

Working files under work/translation/ may hold the Japanese source next to the
English (fields named jp / ja / source); the .en.json copies drop those fields
and any other string that contains Japanese script, except in files that are
allowed to keep UI terms and names (glossary, fixed.json, gfx specs).  Only the
.en.json copies are meant to be committed (see .gitignore).
"""
import glob
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP = {'jp', 'ja', 'source', 'src'}
JP = re.compile('[぀-ヿ㐀-鿿ｦ-ﾟ]')
KEEP_TERMS = ('fixed.json', 'glossary.json', 'gfx_text.json')     # names / UI terms allowed


def strip(v):
    if isinstance(v, dict):
        return {k: strip(x) for k, x in v.items() if k not in DROP and not (isinstance(x, str) and JP.search(x))}
    if isinstance(v, list):
        return [strip(x) for x in v if not (isinstance(x, str) and JP.search(x))]
    return v


def main():
    files = [f for f in glob.glob(os.path.join(ROOT, 'work', 'translation', '**', '*.json'), recursive=True)
             if not f.endswith('.en.json')]
    n = 0
    for f in sorted(files):
        if os.path.basename(f) in KEEP_TERMS:
            continue
        data = json.load(open(f, encoding='utf-8'))
        out = f[:-5] + '.en.json'
        with open(out, 'w', encoding='utf-8') as fh:
            json.dump(strip(data), fh, ensure_ascii=False, indent=1)
            fh.write('\n')
        n += 1
    print('%d .en.json copies written' % n)


if __name__ == '__main__':
    main()
