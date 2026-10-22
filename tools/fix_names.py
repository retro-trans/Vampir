"""Enforce glossary spellings in the English translations (run after agent fixes).

    python tools/fix_names.py [--dry]     -> rewrites work/translation/en/done/*.json and rows

Each rule maps a wrong spelling to the glossary one (whole words). --dry prints the changes.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')
RULES = [
    (r'\bMedovekia\b', 'Medoekia'), (r'\bMedvekia\b', 'Medoekia'),
    (r'\bKarlstadt\b', 'Calstatt'), (r'\bKarlstatt\b', 'Calstatt'), (r'\bCarlstadt\b', 'Calstatt'),
    (r'\bVan Hellsing\b', 'Van Helsing'),
]


def fix(text):
    for a, b in RULES:
        text = re.sub(a, b, text)
    return text


def walk(obj, changes, where):
    if isinstance(obj, dict):
        for k in ('en',):
            if isinstance(obj.get(k), str):
                new = fix(obj[k])
                if new != obj[k]:
                    changes.append((where, obj.get('id'), obj[k], new))
                    obj[k] = new
        for v in obj.get('variants') or []:
            walk(v, changes, where)
    return obj


def main():
    dry = '--dry' in sys.argv
    changes = []
    paths = glob.glob(os.path.join(TR, 'done', '*.json')) + glob.glob(os.path.join(TR, 'rows', '*.json'))
    for p in paths:
        if p.endswith('.en.json'):
            continue
        data = json.load(open(p, encoding='utf8'))
        before = len(changes)
        for r in data:
            walk(r, changes, os.path.basename(p))
        if len(changes) > before and not dry:
            json.dump(data, open(p, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    for c in changes[:40]:
        print('%s %s: %r -> %r' % c)
    print(len(changes), 'changes', '(dry run)' if dry else '')


if __name__ == '__main__':
    main()
