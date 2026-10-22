"""Load work/translation/en/exe_en.tsv (offset<TAB>English) into the EXE rows file."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(ROOT, 'work', 'translation', 'en')
tsv = dict(l.rstrip('\n').split('\t', 1) for l in open(os.path.join(TR, 'exe_en.tsv'), encoding='utf8') if '\t' in l)
p = os.path.join(TR, 'rows', 'SLPS_019.32.json')
rows = json.load(open(p, encoding='utf8'))
n = 0
for r in rows:
    k = r['id'].split('@')[1]
    if k in tsv:
        r['en'] = tsv[k]
        n += 1
json.dump(rows, open(p, 'w', encoding='utf8'), ensure_ascii=False, indent=1)
print(n, 'EXE rows')
