"""Build the Latin font texture (replaces CM/FT1-3.TH4) and its letter metrics.

The game draws text from a 4bpp 768x256 texture loaded at VRAM (704,0). The new
texture holds Noto Sans letters rasterised at 4x the on-screen size (48 texels for
the 12 px line); the VWF hook draws each letter as a POLY_FT4 at 1x, so emulators
that upscale show the full detail. The top-left texel of every 4x4 block holds the
1x rasterisation, which is what a native-resolution GPU samples.

Texel values are 16 coverage levels; the hook's own CLUTs (stored in the same
texture, page 0 rows 248-249 below the last letter row) ramp each text colour
from dark to full.

    python tools/font_atlas.py --preview work/ui/font/atlas.png
"""
import argparse
import json
import os
import struct

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'tools', 'fonts', 'noto-sans', 'NotoSans-Regular.ttf')
EM = 11              # px on screen
S = 4                # texels per screen pixel
LINE = 12            # line box height (px)
BASE = 9             # baseline, px from the line top
TEX_W, TEX_H = 768, 256      # 4bpp texels (3 pages of 256)
VRAM_X = 704                 # 16-bit units
PAGES = 3                    # letter rows at y 0..239 of each page
CLUT_Y = 248                 # CLUT rows (page 0, below the letter rows)
# letter ids: ASCII 0x20-0x7E map to themselves; extras from 0x80
EXTRA = ['‘', '’', '“', '”', '—', '–', '…', 'é', 'è', 'ê', 'à', 'â', 'ç', 'ô', 'û', 'ü',
         'ï', 'ö', 'ä', 'ñ', 'É', '♪', '♥', '«', '»', '·']
# text attribute -> colour (from the original CLUTs, see docs/TEXT_SYSTEM.md)
ATTR_RGB = [(0x60, 0x60, 0x60), (0xE8, 0xE8, 0xE8), (0xF0, 0xF0, 0x00), (0xE8, 0xE8, 0xE8),
            (0xE8, 0xE8, 0xE8), (0x90, 0x48, 0x48), (0xA8, 0xA0, 0x48), (0xE8, 0xE8, 0xE8)]


def letters():
    m = {c: chr(c) for c in range(0x20, 0x7F)}
    for i, ch in enumerate(EXTRA):
        m[0x80 + i] = ch
    return m


def char_to_id():
    return {ch: i for i, ch in letters().items()}


def render(ch, size, scale):
    """Coverage image of `ch` with the pen at x=pad*scale... returns (img, origin_x)."""
    f = ImageFont.truetype(FONT, size)
    pad = 4 * scale
    w = int(f.getlength(ch)) + 2 * pad + 4 * scale
    im = Image.new('L', (w, LINE * scale), 0)
    asc = f.getmetrics()[0]
    ImageDraw.Draw(im).text((pad, BASE * scale - asc), ch, font=f, fill=255)
    return im, pad


def build():
    f1 = ImageFont.truetype(FONT, EM)
    glyphs = {}
    for lid, ch in letters().items():
        adv = max(1, int(round(f1.getlength(ch))))
        if ch == ' ':
            glyphs[lid] = {'ch': ch, 'adv': 3, 'w': 0, 'xoff': 0, 'img': None}
            continue
        hi, ox = render(ch, EM * S, S)
        lo, ox1 = render(ch, EM, 1)
        bb = hi.getbbox()
        if not bb:
            glyphs[lid] = {'ch': ch, 'adv': adv, 'w': 0, 'xoff': 0, 'img': None}
            continue
        x0 = (bb[0] - ox) // S                    # px relative to the pen, floor
        x1 = -((-(bb[2] - ox)) // S)              # ceil
        w = x1 - x0
        cell = Image.new('L', (w * S, LINE * S), 0)
        cell.paste(hi.crop((ox + x0 * S, 0, ox + x1 * S, LINE * S)), (0, 0))
        px = cell.load()
        lpx = lo.load()
        for py in range(LINE):
            for qx in range(w):
                sx = ox1 + x0 + qx
                v = lpx[sx, py] if 0 <= sx < lo.width else 0
                px[qx * S, py * S] = v             # 1x hint texel
        glyphs[lid] = {'ch': ch, 'adv': adv, 'w': w, 'xoff': x0, 'img': cell}
    return glyphs


def pack(glyphs):
    """Shelf-pack 4x cells into pages 0..PAGES-1 (rows of 48 texels, u+w <= 255)."""
    tex = Image.new('L', (TEX_W, TEX_H), 0)
    page, x, y = 0, 0, 0
    order = sorted((g for g in glyphs.items() if g[1]['img'] is not None), key=lambda kv: kv[0])
    for lid, g in order:
        tw = g['w'] * S
        if x + tw > 255:
            x, y = 0, y + LINE * S
            if y + LINE * S > 255:
                page, y = page + 1, 0
                if page >= PAGES:
                    raise SystemExit('font atlas full')
        g['page'], g['u'], g['v'] = page, x, y
        tex.paste(g['img'], (page * 256 + x, y))
        x += tw + 1
    return tex


def clut_words(rgb):
    out = [0]
    r, g, b = rgb
    for k in range(1, 16):
        a = k / 15.0
        c = (int(r * a) >> 3) | ((int(g * a) >> 3) << 5) | ((int(b * a) >> 3) << 10)
        out.append(c if c else 0x8000)          # opaque black, never the transparent 0
    return out


def clut_pos(attr):
    """VRAM (x, y) of the CLUT for a text attribute: page 0, rows 248-249, 4 per row."""
    return VRAM_X + (attr % 4) * 16, CLUT_Y + attr // 4


def clut_id(attr):
    x, y = clut_pos(attr)
    return (y << 6) | (x >> 4)


def th4_bytes(tex, glyphs):
    """4bpp texture bytes (low nibble = left texel) with the CLUTs written in."""
    levels = tex.point(lambda v: (v * 15 + 127) // 255)
    data = bytearray(TEX_W * TEX_H // 2)
    lp = levels.load()
    for yy in range(TEX_H):
        for xx in range(0, TEX_W, 2):
            data[(yy * TEX_W + xx) // 2] = lp[xx, yy] | (lp[xx + 1, yy] << 4)
    for attr, rgb in enumerate(ATTR_RGB):
        x, y = clut_pos(attr)
        off = (y * (TEX_W // 4) + (x - VRAM_X)) * 2
        data[off:off + 32] = struct.pack('<16H', *clut_words(rgb))
    return bytes(data)


def metrics_blob(glyphs):
    """Letter table for the hook: 256 x 8 bytes {u, v, w(px), tpage_lo, xoff(s8), adv, 0, 0}."""
    out = bytearray(256 * 8)
    for lid, g in glyphs.items():
        tp = 0x0B + g.get('page', 0)
        struct.pack_into('<BBBBbBBB', out, lid * 8, g.get('u', 0), g.get('v', 0), g['w'], tp,
                         g['xoff'], g['adv'], 0, 0)
    return bytes(out)


def make():
    glyphs = build()
    tex = pack(glyphs)
    return glyphs, tex, th4_bytes(tex, glyphs), metrics_blob(glyphs)


def advances():
    return {g['ch']: g['adv'] for g in build().values()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preview')
    ap.add_argument('--out', default=os.path.join(ROOT, 'work', 'output', 'font'))
    a = ap.parse_args()
    glyphs, tex, th4, met = make()
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, 'FT.TH4'), 'wb').write(th4)
    open(os.path.join(a.out, 'letters.bin'), 'wb').write(met)
    json.dump({g['ch']: {'id': lid, 'adv': g['adv'], 'w': g['w'], 'xoff': g['xoff'],
                         'page': g.get('page'), 'u': g.get('u'), 'v': g.get('v')}
               for lid, g in glyphs.items()},
              open(os.path.join(a.out, 'letters.json'), 'w', encoding='utf8'), ensure_ascii=False, indent=0)
    print('letters', len(glyphs), 'TH4', len(th4))
    if a.preview:
        os.makedirs(os.path.dirname(a.preview), exist_ok=True)
        tex.save(a.preview)


if __name__ == '__main__':
    main()
