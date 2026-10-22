"""Tile screenshots into one contact sheet: python tools/contact.py out.png in1.png in2.png ... [--cols 3]"""
import sys
from PIL import Image
args = sys.argv[1:]
cols = 3
if '--cols' in args:
    i = args.index('--cols'); cols = int(args[i + 1]); del args[i:i + 2]
out, ins = args[0], args[1:]
ims = [Image.open(p).convert('RGB') for p in ins]
w, h = ims[0].size
rows = (len(ims) + cols - 1) // cols
c = Image.new('RGB', (w * cols, h * rows))
for i, im in enumerate(ims):
    c.paste(im, ((i % cols) * w, (i // cols) * h))
c.save(out)
