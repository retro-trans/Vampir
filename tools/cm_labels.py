"""Find framed text buttons in CM/CM.TH4 (4bpp, VRAM 320,256, 1024x256 texels).

    python tools/cm_labels.py detect   -> work/ui/cm_buttons.json + work/ui/tims/_buttons.png
A button: a constant run (>= 12 texels) on its top row, a constant run on a row 8-21 below
(the bottom frame), and an interior whose most common index (fill) differs from both;
text = interior pixels brighter than the fill (indices > fill on these grey-ramp CLUTs).
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc', 'CM', 'CM.TH4')


def load():
    d = open(SRC, 'rb').read()
    a = np.frombuffer(d, dtype=np.uint8)
    px = np.zeros(len(d) * 2, np.uint8)
    px[0::2] = a & 15
    px[1::2] = a >> 4
    return px.reshape(256, 1024).astype(int)


def detect(img):
    H, W = img.shape
    found = []
    for y in range(H - 8):
        x = 0
        while x < W:
            v = img[y, x]
            x2 = x
            while x2 < W and img[y, x2] == v:
                x2 += 1
            L = x2 - x
            if v != 0 and L >= 12:
                for k in range(8, 22):
                    if y + k >= H:
                        break
                    bot = img[y + k, x + 2:x2 - 2]
                    if len(set(bot.tolist())) == 1 and bot[0] != v:
                        inner = img[y + 2:y + k - 1, x + 2:x2 - 2]
                        vals, cnt = np.unique(inner, return_counts=True)
                        fill = vals[cnt.argmax()]
                        txt = inner > fill
                        if fill not in (v, bot[0]) and txt.sum() >= 12 and cnt.max() > inner.size * 0.4:
                            found.append([int(x), int(y), int(L), int(k + 1), int(fill)])
                            break
            x = x2
    uniq = []
    for b in found:
        if not any(abs(b[0] - u[0]) < 4 and abs(b[1] - u[1]) < 4 for u in uniq):
            uniq.append(b)
    return uniq


def sheet(img, boxes, path):
    W2 = 1000
    crops = [(i, Image.fromarray((img[y:y + h, x:x + w] * 17).astype(np.uint8)).resize((w * 3, h * 3), Image.NEAREST))
             for i, (x, y, w, h, f) in enumerate(boxes)]
    out = Image.new('RGB', (W2, 2400), (40, 0, 40))
    dr = ImageDraw.Draw(out)
    cx, cy, rh = 0, 0, 0
    for i, c in crops:
        if cx + c.width + 30 > W2:
            cx, cy, rh = 0, cy + rh + 14, 0
        out.paste(c, (cx + 24, cy + 12))
        dr.text((cx, cy + 12), str(i), fill=(0, 255, 0))
        cx += c.width + 30
        rh = max(rh, c.height)
    out.crop((0, 0, W2, cy + rh + 20)).save(path)


if __name__ == '__main__':
    img = load()
    b = detect(img)
    json.dump(b, open(os.path.join(ROOT, 'work', 'ui', 'cm_buttons.json'), 'w'))
    sheet(img, b, os.path.join(ROOT, 'work', 'ui', 'tims', '_buttons.png'))
    print(len(b), 'buttons')
