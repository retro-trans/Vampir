"""Read DuckStation save states (format 'DUCC', zstd data): RAM and VRAM.

Needs 64-bit Python (loads DuckStation's zstd.dll):  py -3.11 tools/dsstate.py ...

    ram  <state> <out.bin>                      2 MiB main RAM
    vram <state> <out.png>                      1024x512 16-bit view (RGB)
    vram4 <state> <out.png> x y w h [scale]     4bpp view of a VRAM rect (x,w in
                                                16-bit units), palette index as gray
    vrambin <state> <out.bin>                   raw 1 MiB VRAM
Stdlib only.
"""
import ctypes
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZSTD = os.path.join(ROOT, 'work', 'emulator', 'duckstation', 'zstd.dll')
VRAM_SIZE = 1024 * 512 * 2
RAM_SIZE = 2 * 1024 * 1024


def load(path):
    d = open(path, 'rb').read()
    if d[:4] != b'DUCC':
        raise ValueError('not a DuckStation state')
    ctype, csize, usize, off = struct.unpack_from('<4I', d, 0xC8)
    blob = d[off:off + csize]
    if ctype == 0:
        return blob
    z = ctypes.CDLL(ZSTD)
    z.ZSTD_decompress.restype = ctypes.c_size_t
    z.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    out = ctypes.create_string_buffer(usize)
    n = z.ZSTD_decompress(out, usize, blob, len(blob))
    if n != usize:
        raise IOError('zstd failed: %d' % n)
    return out.raw


def marker_data(blob, name, size):
    i = blob.find(name)
    if i < 0:
        raise ValueError('marker %r not found' % name)
    return blob[i + len(name):i + len(name) + size]


def ram(blob):
    i = blob.find(b'Bus')
    # RAM follows the Bus marker after a few fields; locate by size of block
    # ending right before the DMA marker.
    j = blob.find(b'DMA', i)
    return blob[j - 4 - RAM_SIZE - 0x2E + 0x2E:j][-RAM_SIZE - 0x31:-0x31] if False else _ram_scan(blob, i)


def _ram_scan(blob, start):
    # The RAM image starts with the BIOS exception area; at 0x80 it holds
    # the standard handler 'lui k0,0' — find the first such 2 MiB window.
    for off in range(start, start + 0x400):
        if blob[off + 0x80:off + 0x84] == bytes.fromhex('00001a3c'):
            return blob[off:off + RAM_SIZE]
    raise ValueError('RAM not found')


def vram(blob):
    return marker_data(blob, b'GPU-VRAM', VRAM_SIZE)


def write_png(path, w, h, rows, mode='RGB'):
    ct = {'RGB': 2, 'L': 0}[mode]
    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(t, data):
        c = struct.pack('>I', len(data)) + t + data
        return c + struct.pack('>I', zlib.crc32(t + data) & 0xFFFFFFFF)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, ct, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b'')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, 'wb').write(png)


def vram16_png(v, path):
    rows = []
    for y in range(512):
        px = struct.unpack_from('<1024H', v, y * 2048)
        r = bytearray()
        for p in px:
            r += bytes(((p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3))
        rows.append(bytes(r))
    write_png(path, 1024, 512, rows)


def vram4_png(v, path, x, y, w, h, scale=1):
    rows = []
    for yy in range(y, y + h):
        r = bytearray()
        for xx in range(x, x + w):
            p = struct.unpack_from('<H', v, yy * 2048 + xx * 2)[0]
            for k in range(4):
                r += bytes([((p >> (4 * k)) & 15) * 17]) * scale
        for _ in range(scale):
            rows.append(bytes(r))
    write_png(path, w * 4 * scale, h * scale, rows, 'L')


def main():
    op, path = sys.argv[1], sys.argv[2]
    blob = load(path)
    if op == 'ram':
        open(sys.argv[3], 'wb').write(_ram_scan(blob, blob.find(b'Bus')))
    elif op == 'vrambin':
        open(sys.argv[3], 'wb').write(vram(blob))
    elif op == 'vram':
        vram16_png(vram(blob), sys.argv[3])
    elif op == 'fb':
        # 16-bit crop, e.g. a framebuffer: fb <state> <out.png> x y w h [scale]
        x, y, w, h = (int(a, 0) for a in sys.argv[4:8])
        scale = int(sys.argv[8]) if len(sys.argv) > 8 else 1
        v = vram(blob)
        rows = []
        for yy in range(y, y + h):
            r = bytearray()
            for p in struct.unpack_from('<%dH' % w, v, yy * 2048 + x * 2):
                r += bytes(((p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3)) * scale
            rows += [bytes(r)] * scale
        write_png(sys.argv[3], w * scale, h * scale, rows)
    elif op == 'vram4':
        x, y, w, h = (int(a, 0) for a in sys.argv[4:8])
        scale = int(sys.argv[8]) if len(sys.argv) > 8 else 1
        vram4_png(vram(blob), sys.argv[3], x, y, w, h, scale)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
