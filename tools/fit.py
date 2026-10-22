"""Measure English text against the game's line width (Noto Sans 11 px VWF).

    python tools/fit.py "text" ["more text" ...]
        prints the pixel width of each line (lines split on ' / '), {PLAYER_NAME} and
        {PARTNER_NAME} counted as 8 letters, and how many box lines it wraps to.
Dialogue box: 240 px per line, 3 lines.  Full-page text: 264 px, 12 lines.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font_atlas  # noqa: E402

ADV = font_atlas.advances()
NAME = 'Christop'
WIDTH = 240


def width(t):
    t = t.replace('{PLAYER_NAME}', NAME).replace('{PARTNER_NAME}', NAME)
    return sum(ADV.get(c, 6) for c in t)


_DICT = []


def cells(word):
    """Grid cells (tokens) a word takes; names are stored letter by letter."""
    if not _DICT:
        import glob
        import vtext
        found = sorted(glob.glob(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                              'work', 'output', '*', 'dictionary.json')), key=os.path.getmtime)
        _DICT.append(vtext.Dictionary.load(found[-1]) if found else None)
    d = _DICT[0]
    if d is None or not word:
        return len(word)
    try:
        return len(d.tokenize(word))
    except Exception:
        return len(word)


def wrap(t, w=WIDTH):
    """Number of box lines the text takes with the game's word wrap: a line ends when the next
    word does not fit in w pixels or in the line's grid cells (28 per line)."""
    t = t.replace('{PLAYER_NAME}', NAME).replace('{PARTNER_NAME}', NAME)
    maxc = 28                            # grid cells per line (dialogue box patched to 28)
    lines, x, c = 1, 0, 0
    for i, word in enumerate(t.split(' ')):
        ww, wc = width(word), cells(word)
        sp, sc = (ADV[' '], 1) if i else (0, 0)
        if (x or c) and (x + sp + ww > w or c + sc + wc > maxc):
            lines += 1
            x, c = ww, wc
        else:
            x += sp + ww
            c += sc + wc
    return lines


def report(text, w=WIDTH):
    out = []
    for line in text.split(' / '):
        out.append('%3d px  %d line(s)  %s' % (width(line), wrap(line, w), line))
    return '\n'.join(out)


if __name__ == '__main__':
    for a in sys.argv[1:]:
        print(report(a))
