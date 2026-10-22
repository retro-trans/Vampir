"""Scan binary files for Shift-JIS Japanese text runs.

Text in this game appears in two layouts:
  be - normal Shift-JIS byte order (IMDATA/SCRIPT.BIN, TACTICS/HEXMAP.BIN, ...)
  le - each 16-bit word byte-swapped (strings inside the .EXE files)

Usage: python tools/find_sjis.py <dir> [--min N] [--out file.tsv]
Prints per-file counts of runs that look like real text (filtered against
graphics/video noise); --out writes file/offset/layout/text rows. The output
contains Japanese, so keep it under work/source/ (git-ignored).
"""
import argparse
import os
import re

GOOD_PUNCT = set('　、。，．・：；？！ー～…‥「」『』（）［］【】〈〉＋－＝％＆＊＠／々ヶヴ')
KANA = re.compile(r'[ぁ-ゖァ-ヺー]')


def is_lead(b):
    return 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xEF


def is_trail(b):
    return 0x40 <= b <= 0xFC and b != 0x7F


def char_ok(pair, ch):
    """Character plausible in game text (kana, punct, alnum, level-1 kanji)."""
    if ch in GOOD_PUNCT or KANA.match(ch):
        return True
    if '０' <= ch <= 'ｚ':  # fullwidth digits / latin
        return True
    if 0x88 <= pair[0] <= 0x98:  # JIS level-1 kanji (common)
        return True
    return False


def looks_like_text(pairs, text):
    n = len(text)
    good = sum(char_ok(p, c) for p, c in zip(pairs, text))
    kana = len(KANA.findall(text))
    if good < n * 0.9:
        return False
    body = text.replace('　', '')  # full-width space is common padding
    if not body.strip('・ー'):
        return True
    top = max(body.count(c) for c in set(body))
    if top > max(2, len(body) * 0.5):
        return False
    # need some kana unless short kanji term like 攻撃力
    if kana == 0 and n > 6:
        return False
    return True


def runs(data, min_chars):
    i, n = 0, len(data)
    while i < n - 1:
        if not (is_lead(data[i]) and is_trail(data[i + 1])):
            i += 1
            continue
        start, pairs, chars = i, [], []
        while i < n - 1 and is_lead(data[i]) and is_trail(data[i + 1]):
            try:
                chars.append(data[i:i + 2].decode('cp932'))
            except UnicodeDecodeError:
                break
            pairs.append(data[i:i + 2])
            i += 2
        text = ''.join(chars)
        if len(chars) >= min_chars and looks_like_text(pairs, text):
            yield start, text
        if i == start:
            i += 1


def swap16(data, align):
    b = bytearray(data[align:])
    b = b[:len(b) // 2 * 2]
    b[0::2], b[1::2] = b[1::2], b[0::2]
    return bytes(b)


HIRA = re.compile(r'[ぁ-ゖ]')


def confidence(text):
    """'high' = sentence-like (hiragana-rich), 'low' = short or kanji-only."""
    text = text.replace('　', '')
    hira = len(HIRA.findall(text))
    kana = len(KANA.findall(text))
    if len(text) >= 4 and (hira >= len(text) * 0.25 or kana >= len(text) * 0.6):
        return 'high'
    return 'low'


def score(text):
    return len(HIRA.findall(text)) * 2 + len(KANA.findall(text)) + len(text) * 0.1


def scan(data, min_chars):
    hits = [(off, 'be', t) for off, t in runs(data, min_chars)]
    for align in (0, 1):
        for off, t in runs(swap16(data, align), min_chars):
            if off % 2 == 0:  # swapped text must start on a word boundary
                hits.append((off + align, 'le', t))
    # Byte-ranges claimed by both layouts: keep the more text-like reading.
    hits.sort(key=lambda h: -score(h[2]))
    taken = bytearray(len(data) + 1)
    for off, mode, t in hits:
        end = off + len(t) * 2
        if any(taken[off:end]):
            continue
        taken[off:end] = b'\x01' * (end - off)
        yield off, mode, confidence(t), t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dir')
    ap.add_argument('--min', type=int, default=3)
    ap.add_argument('--out')
    a = ap.parse_args()
    rows = []
    for root, _, files in os.walk(a.dir):
        for fn in sorted(files):
            if fn.startswith('_'):
                continue
            p = os.path.join(root, fn)
            data = open(p, 'rb').read()
            hits = sorted(scan(data, a.min))
            rel = os.path.relpath(p, a.dir).replace(os.sep, '/')
            cols = []
            for mode in ('be', 'le'):
                hi = [h for h in hits if h[1] == mode and h[2] == 'high']
                lo = [h for h in hits if h[1] == mode and h[2] == 'low']
                cols.append(f'{mode}: high {len(hi):6d} ({sum(len(h[3]) for h in hi):7d} ch)'
                            f' low {len(lo):5d}')
            print(f'{rel:24s} ' + '   '.join(cols))
            rows += [(rel,) + h for h in hits]
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as o:
            for rel, off, m, c, t in rows:
                o.write(f'{rel}\t0x{off:08X}\t{m}\t{c}\t{t}\n')


if __name__ == '__main__':
    main()
