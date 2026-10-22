"""Re-render Japanese text baked into TIM graphics (spec: work/ui/gfx_text.json).

    python tools/gfx.py preview      -> work/ui/gfx_preview/*.png (original | new)
    gfx.patch(files)                 -> {disc path: patched bytes} for tools/build.py

Spec entries:
  {"file": "DC/DOP.DAT", "off": "0x40", "kind": "strip", "text": "...", "size": 15}
      4bpp strip with a grey ramp CLUT: white antialiased text, centred.
  {"file": "DC/OPN.DAT", "off": "0x41438", "kind": "logo", "text": "Vampir", ...}
      8bpp title logo: gradient-filled gothic lettering with a dark outline.
  {"file": ..., "kind": "subtitle", "text": ..., "box": [x, y, w, h]}
      4bpp picture: text drawn into box with the CLUT's existing colour ramp (index 1 clear).
"""
import json
import os
import struct
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tim  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'source', 'disc')
SPEC = os.path.join(ROOT, 'work', 'ui', 'gfx_text.json')
FONTS = {
    'serif': 'C:/Windows/Fonts/constan.ttf',
    'serif_i': 'C:/Windows/Fonts/constani.ttf',
    'gothic': 'C:/Windows/Fonts/OLDENGL.TTF',
    'sans': os.path.join(ROOT, 'tools', 'fonts', 'noto-sans', 'NotoSans-Regular.ttf'),
}


def font(name, size):
    return ImageFont.truetype(FONTS.get(name, name), size)


def text_alpha(text, w, h, f, ss=4, dy=0, margin=6, metrics=False):
    """Antialiased coverage of text centred in w x h (supersampled)."""
    size = f.size
    im = Image.new('L', (w * ss, h * ss), 0)
    dr = ImageDraw.Draw(im)
    while True:                           # shrink until it fits with a 6 px margin
        big = ImageFont.truetype(f.path, size * ss)
        bb = dr.textbbox((0, 0), text, font=big)
        if bb[2] - bb[0] <= (w - margin) * ss or size <= 7:
            break
        size -= 1
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if metrics:                           # same baseline for every label (cap height centred)
        cb = dr.textbbox((0, 0), 'H', font=big)
        th, top = cb[3] - cb[1], cb[1]
    else:
        top = bb[1]
    dr.text(((w * ss - tw) // 2 - bb[0], (h * ss - th) // 2 - top + dy * ss), text, font=big, fill=255)
    return im.resize((w, h), Image.LANCZOS)


def put_4bpp(t, idx):
    w, h = t['w'], t['h']
    out = bytearray(len(t['data']))
    px = idx.load()
    for y in range(h):
        for x in range(0, w, 2):
            out[y * (w // 2) + x // 2] = (px[x, y] & 15) | ((px[x + 1, y] & 15) << 4)
    return bytes(out)


def render_strip(t, e):
    a = text_alpha(e['text'], t['w'], t['h'], font(e.get('font', 'serif'), e.get('size', 15)))
    idx = a.point(lambda v: (v * 15 + 127) // 255)
    return put_4bpp(t, idx), None


def render_subtitle(t, e):
    """Draw text into a box of a 4bpp picture using its clear index and its colour ramp."""
    clut = t['clut'][0]
    clear = e.get('clear', 1)
    lum = lambda c: (c & 31) + ((c >> 5) & 31) + ((c >> 10) & 31)
    ramp = sorted((i for i in range(16) if i != clear and clut[i] != 0), key=lambda i: lum(clut[i]))
    w, h = t['w'], t['h']
    idx = Image.new('L', (w, h), clear)
    bx, by, bw, bh = e['box']
    a = text_alpha(e['text'], bw, bh, font(e.get('font', 'serif'), e.get('size', 14)))
    px, pa = idx.load(), a.load()
    for y in range(bh):
        for x in range(bw):
            v = pa[x, y]
            if v > 40:
                px[bx + x, by + y] = ramp[min(len(ramp) - 1, v * len(ramp) // 256)]
    return put_4bpp(t, idx), None


def render_logo(t, e):
    w, h = t['w'], t['h']
    f = font(e.get('font', 'gothic'), e.get('size', 64))
    a = text_alpha(e['text'], w, h, f, dy=e.get('dy', 0))
    outline = a.filter(ImageFilter.MaxFilter(5))
    # vertical gradient: deep red -> orange -> gold
    grad = Image.new('RGB', (w, h))
    gp = grad.load()
    stops = [(0.0, (255, 236, 140)), (0.4, (250, 140, 50)), (0.75, (215, 50, 25)), (1.0, (150, 15, 15))]
    for y in range(h):
        p = y / max(1, h - 1)
        for k in range(len(stops) - 1):
            if stops[k][0] <= p <= stops[k + 1][0]:
                u = (p - stops[k][0]) / (stops[k + 1][0] - stops[k][0])
                c = tuple(int(stops[k][1][i] + (stops[k + 1][1][i] - stops[k][1][i]) * u) for i in range(3))
        for x in range(w):
            gp[x, y] = c
    img = Image.new('RGB', (w, h), (0, 0, 0))
    dark = Image.new('RGB', (w, h), (40, 6, 6))
    img.paste(dark, (0, 0), outline)
    img.paste(grad, (0, 0), a)
    mask = outline.point(lambda v: 255 if v > 60 else 0)
    q = img.quantize(colors=255, method=Image.MEDIANCUT)
    pal = q.getpalette()[:255 * 3]
    qi = q.load()
    mi = mask.load()
    data = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            data[y * w + x] = 0 if not mi[x, y] else qi[x, y] + 1
    clut = [0]
    for i in range(255):
        r, g, b = pal[i * 3:i * 3 + 3]
        c = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
        clut.append(c | 0x8000)               # opaque even when black
    return bytes(data), clut


def render_lines(t, e):
    """4bpp list picture with a grey-ramp CLUT (staff credit roles): one text line per band of
    `pitch` rows from `top`; a band whose entry is null keeps its pixels.  Left-aligned."""
    w, h = t['w'], t['h']
    idx = Image.new('L', (w, h), 0)
    px = idx.load()
    src = t['data']
    for y in range(h):
        for x in range(w):
            px[x, y] = (src[y * (w // 2) + x // 2] >> ((x & 1) * 4)) & 15
    top, pitch, bh = e.get('top', 1), e.get('pitch', 12), e.get('band', 11)
    f = font(e.get('font', 'serif'), e.get('size', 11))
    ss = 4
    for i, text in enumerate(e['lines']):
        if text is None:
            continue
        y0 = top + i * pitch
        for y in range(y0, min(h, y0 + pitch)):        # the whole pitch: glyphs reach the gap row
            for x in range(w):
                px[x, y] = 0
        big = ImageFont.truetype(f.path, f.size * ss)
        im = Image.new('L', (w * ss, bh * ss), 0)
        dr = ImageDraw.Draw(im)
        cb = dr.textbbox((0, 0), 'H', font=big)
        dr.text((e.get('x', 1) * ss, (bh * ss - (cb[3] - cb[1])) // 2 - cb[1]), text, font=big, fill=255)
        a = im.resize((w, bh), Image.LANCZOS).load()
        for y in range(bh):
            for x in range(w):
                if y0 + y < h:
                    px[x, y0 + y] = (a[x, y] * 15 + 127) // 255
    return put_4bpp(t, idx), None


KINDS = {'strip': render_strip, 'logo': render_logo, 'subtitle': render_subtitle, 'lines': render_lines}


def spec():
    return json.load(open(SPEC, encoding='utf8'))


def patch(src_dir=DISC):
    out = {}
    for e in spec():
        if not e.get('text'):
            continue
        name = e['file']
        d = bytearray(out.get(name) or open(os.path.join(src_dir, name), 'rb').read())
        off = int(e['off'], 16)
        t = tim.parse(bytes(d), off)
        pix, clut = KINDS[e['kind']](t, e)
        assert len(pix) == len(t['data'])
        d[t['data_off']:t['data_off'] + len(pix)] = pix
        if clut:
            co = off + 8 + 12
            n = len(t['clut'][0])
            assert n == len(clut), (n, len(clut))
            d[co:co + 2 * n] = struct.pack('<%dH' % n, *clut)
        out[name] = bytes(d)
    if os.path.exists(BUTTONS):
        out['CM/CM.TH4'] = cm_patch(open(os.path.join(src_dir, 'CM', 'CM.TH4'), 'rb').read())
    return out


def preview():
    od = os.path.join(ROOT, 'work', 'ui', 'gfx_preview')
    os.makedirs(od, exist_ok=True)
    new = patch()
    for e in spec():
        if not e.get('text') or 'off' not in e:
            continue
        off = int(e['off'], 16)
        a = tim.to_image(tim.parse(open(os.path.join(DISC, e['file']), 'rb').read(), off))
        b = tim.to_image(tim.parse(new[e['file']], off))
        c = Image.new('RGB', (a.width, a.height * 2 + 2), (255, 0, 255))
        c.paste(a, (0, 0))
        c.paste(b, (0, a.height + 2))
        c.save(os.path.join(od, '%s_%s.png' % (e['file'].replace('/', '_'), e['off'])))
    print(len(new), 'files')



# ---------------------------------------------------------------- CM.TH4 buttons (raw 4bpp)
CM_W = 1024        # texels per row (VRAM 320,256, 256 units wide)
BUTTONS = os.path.join(ROOT, 'work', 'ui', 'cm_labels.json')


def cm_patch(data):
    """Rewrite button labels in CM.TH4: erase the text (indices above the fill) and draw the
    English with the grey ramp fill+1..15 by coverage."""
    import numpy as np
    spec_b = json.load(open(BUTTONS, encoding='utf8'))
    a = np.frombuffer(data, dtype=np.uint8)
    px = np.zeros(len(data) * 2, np.uint8)
    px[0::2] = a & 15
    px[1::2] = a >> 4
    img = px.reshape(-1, CM_W).copy()
    spec_b = sorted(spec_b, key=lambda b: not b.get('erase'))     # erase-only areas first
    for b in spec_b:
        if not b.get('en') and not b.get('erase'):
            continue
        x, y, w, h = b['box']
        dark = b.get('dark', False)          # dark text on a light bar (word strips)
        if dark or b.get('exact'):
            ix0, iy0, ix1, iy1 = x, y, x + w, y + h
        else:
            ix0, iy0, ix1, iy1 = x + 1, y + 2, x + w - 1, y + h - 2
        inner = img[iy0:iy1, ix0:ix1]
        vals, cnt = np.unique(inner, return_counts=True)
        fill = b.get('fill', int(vals[cnt.argmax()]))
        if dark:
            low = int(inner.min())
            inner[inner < fill] = fill
        else:
            inner[inner > fill] = fill
        if not b.get('en'):
            continue
        f = font(b.get('font', 'sans'), b.get('size', 10))
        cov = text_alpha(b['en'], ix1 - ix0, iy1 - iy0, f, dy=b.get('dy', 0), margin=2, metrics=True)
        c = np.array(cov, dtype=np.int32)
        top = b.get('top', 1 if dark else 15)
        lv = fill + (c * (top - fill) + (127 if top >= fill else -127)) // 255
        inner[:] = np.where(c > 24, lv, inner)
    flat = img.reshape(-1)
    return bytes((flat[0::2] | (flat[1::2] << 4)).astype(np.uint8))


if __name__ == '__main__':
    preview()
