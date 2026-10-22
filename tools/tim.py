"""PlayStation TIM images inside the disc files: scan, convert, contact sheets.

    python tools/tim.py scan  <file>                 list TIMs (offset, bpp, VRAM pos, size)
    python tools/tim.py dump  <file> <outdir>         every TIM -> <outdir>/<offset>.png (CLUT 0)
    python tools/tim.py sheet <file> <out.png> [w]    contact sheet of all TIMs, labelled
Paths are disc paths under work/source/disc (e.g. IMDATA/MATI.BIN).
"""
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISC = os.path.join(ROOT, 'work', 'source', 'disc')


def scan(d):
    """[(offset, info)] where info has bpp, clut (list of palettes), x, y, w (pixels), h, data, end."""
    out = []
    i = 0
    while True:
        i = d.find(b'\x10\x00\x00\x00', i)
        if i < 0 or i + 8 > len(d):
            break
        if i % 4 == 0:
            t = parse(d, i)
            if t:
                out.append((i, t))
                i = t['end']
                continue
        i += 4
    return out


def parse(d, i):
    flag = struct.unpack_from('<I', d, i + 4)[0]
    if flag not in (0, 1, 2, 3, 8, 9):
        return None
    o = i + 8
    clut = []
    cx = cy = None
    if flag & 8:
        if o + 12 > len(d):
            return None
        ln, cx, cy, cw, ch = struct.unpack_from('<IHHHH', d, o)
        if not (12 < ln < 0x10000 and ln == 12 + cw * ch * 2 and cx < 1024 and cy < 512 and cw and ch):
            return None
        for r in range(ch):
            clut.append(struct.unpack_from('<%dH' % cw, d, o + 12 + r * cw * 2))
        o += ln
    if o + 12 > len(d):
        return None
    ln, x, y, w, h = struct.unpack_from('<IHHHH', d, o)
    if not (12 < ln <= 0x100000 and ln == 12 + w * h * 2 and x < 1024 and y < 512 and w and 0 < h <= 512):
        return None
    if o + ln > len(d):
        return None
    bpp = {0: 4, 1: 8, 2: 16, 3: 24}[flag & 3]
    pw = {4: w * 4, 8: w * 2, 16: w, 24: w * 2 // 3}[bpp]
    return {'flag': flag, 'bpp': bpp, 'clut': clut, 'cx': cx, 'cy': cy, 'x': x, 'y': y,
            'w': pw, 'h': h, 'data': d[o + 12:o + ln], 'data_off': o + 12, 'end': o + ln}


def rgb(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)


def to_image(t, pal=0):
    from PIL import Image
    w, h, d = t['w'], t['h'], t['data']
    img = Image.new('RGB', (w, h))
    px = img.load()
    clut = t['clut'][pal] if t['clut'] else None
    for yy in range(h):
        for xx in range(w):
            if t['bpp'] == 4:
                b = d[yy * (w // 2) + xx // 2]
                v = (b >> 4) if xx & 1 else (b & 15)
                c = clut[v] if clut else v * 0x0842
            elif t['bpp'] == 8:
                v = d[yy * w + xx]
                c = clut[v] if clut and v < len(clut) else v * 0x0421
            elif t['bpp'] == 16:
                c = struct.unpack_from('<H', d, (yy * w + xx) * 2)[0]
            else:
                o = (yy * w + xx) * 3
                px[xx, yy] = tuple(d[o:o + 3])
                continue
            px[xx, yy] = rgb(c)
    return img


def main():
    op, path = sys.argv[1], sys.argv[2]
    d = open(os.path.join(DISC, path), 'rb').read()
    ts = scan(d)
    if op == 'scan':
        for off, t in ts:
            print('%08x %2dbpp %3dx%3d at (%d,%d) clut %s' % (off, t['bpp'], t['w'], t['h'], t['x'], t['y'],
                                                            (t['cx'], t['cy'], len(t['clut'])) if t['clut'] else '-'))
    elif op == 'dump':
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        for off, t in ts:
            to_image(t).save(os.path.join(out, '%08x.png' % off))
    elif op == 'sheet':
        from PIL import Image, ImageDraw
        out = sys.argv[3]
        width = int(sys.argv[4]) if len(sys.argv) > 4 else 1024
        imgs = [(off, to_image(t)) for off, t in ts]
        x = y = rowh = 0
        place = []
        for off, im in imgs:
            if x + im.width > width and x:
                x, y = 0, y + rowh + 12
                rowh = 0
            place.append((x, y, off, im))
            x += im.width + 4
            rowh = max(rowh, im.height)
        sheet = Image.new('RGB', (width, y + rowh + 12), (40, 0, 40))
        dr = ImageDraw.Draw(sheet)
        for x, y, off, im in place:
            sheet.paste(im, (x, y + 12))
            dr.text((x, y), '%x' % off, fill=(255, 255, 0))
        sheet.save(out)
        print(out, sheet.size, len(imgs), 'images')


if __name__ == '__main__':
    main()
