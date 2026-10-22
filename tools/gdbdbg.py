"""Drive the game through DuckStation's GDB server: virtual pad + VRAM grabs.

Works while the desktop is locked (no window focus needed).

    python tools/gdbdbg.py run "press circle 4; wait 90; shot work/ui/shots/x.png"

Commands (';' separated):
  press <btn>[+<btn>...] [frames=4]   hold buttons for N PadRead calls, then release 4 frames
  wait <frames>                       let N PadRead calls pass
  shot <out.png> [x y w h]            grab VRAM rect (default: displayed framebuffer)
  vram <out.png>                      whole 1024x512 VRAM (16-bit view)
  which                               print the running EXE
Buttons: up down left right circle cross square triangle start select l1 r1 l2 r2

Mechanism: a breakpoint at the end of the running EXE's PadRead (after its
'nor v0') lets us OR button bits into v0.  For grabs we stop there, save
RAM + registers, run StoreImage+DrawSync from a 5-instruction stub, read the
pixels, then restore everything, so the game never notices.
"""
import struct
import sys
import os
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gdbmem import Gdb      # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BTN = {'l2': 0x1, 'r2': 0x2, 'l1': 0x4, 'r1': 0x8, 'triangle': 0x10, 'circle': 0x20,
       'cross': 0x40, 'square': 0x80, 'select': 0x100, 'start': 0x800,
       'up': 0x1000, 'right': 0x2000, 'down': 0x4000, 'left': 0x8000}
EXES = ['SLPS_019.32']
STUB = 0x8000B900               # kernel RAM, unused in Vampir (0x8000B800-0x8000DBFF are zero)
SCRATCH = 0x8000BA00
SCRATCH_MAX = 0x8000DB00 - SCRATCH - 16


def exe_info(name):
    """Find PadRead end, StoreImage and DrawSync in an EXE by pattern."""
    if name == 'SLPS_019.32':
        # Vampir: pad state built at 0x80014600 (nor v0 = ~(b2<<8|b3)); bp on the 'sh v0,(a0)'
        # that stores it, a3 = port index. libgpu: StoreImage/DrawSync found by name below.
        info = _exe_info_gpu(name)
        info['pad_bp'] = 0x80014610
        return info
    return _exe_info_full(name)


def _exe_info_gpu(name):
    d = open(os.path.join(ROOT, 'work', 'source', 'disc', name), 'rb').read()
    base = struct.unpack_from('<I', d, 0x18)[0]
    body = d[0x800:]
    n = len(body) // 4
    w = struct.unpack_from('<%dI' % n, body)
    o = d.find(b'StoreImage\x00')
    addr = base + o - 0x800
    hi, lo = (addr + 0x8000) >> 16, addr & 0xFFFF
    store = None
    for i in range(n - 1):
        if w[i] == (0x3C040000 | hi) and w[i + 1] == (0x24840000 | lo):
            a = i
            while (w[a] >> 16) != 0x27BD:
                a -= 1
            store = base + a * 4
            break
    return {'store': store, 'drawsync': 0x80068C88}   # DrawSync found via its 'DrawSync(%d)...' string


def _exe_info_full(name):
    d = open(os.path.join(ROOT, 'work', 'source', 'disc', name), 'rb').read()
    base = struct.unpack_from('<I', d, 0x18)[0]
    body = d[0x800:]
    n = len(body) // 4
    w = struct.unpack_from('<%dI' % n, body)
    # BIOS B(16h) stub
    b16 = None
    for i in range(n - 2):
        if w[i] == 0x240A00B0 and w[i + 1] == 0x01400008 and w[i + 2] == 0x24090016:
            b16 = base + i * 4
    jal = 0x0C000000 | ((b16 >> 2) & 0x3FFFFFF)
    pad_bp = None
    for i in range(n - 8):
        if w[i] == jal:
            for k in range(2, 8):
                if w[i + k] == 0x00021027:          # nor v0, zero, v0
                    pad_bp = base + (i + k + 1) * 4
                    break
    # libgpu functions pass their name string to the queue routine
    def by_name(s):
        o = d.find(s.encode() + b'\x00')
        addr = base + o - 0x800
        hi, lo = (addr + 0x8000) >> 16, addr & 0xFFFF
        for i in range(n - 1):
            if w[i] == (0x3C040000 | hi) and w[i + 1] == (0x24840000 | lo):
                a = i
                while (w[a] >> 16) != 0x27BD:
                    a -= 1
                return base + a * 4
    store = by_name('StoreImage')
    # same libgpu build everywhere: LoadImage = StoreImage - 0x64, DrawSync = LoadImage - 0x228
    return {'pad_bp': pad_bp, 'store': store, 'drawsync': store - 0x64 - 0x228}


class Dbg:
    def __init__(self):
        self.g = Gdb()
        self.exe = self.which()
        self.info = exe_info(self.exe)
        self.bp = self.info['pad_bp']
        self.g.cmd('Z0,%x,4' % self.bp)

    def which(self):
        ram = self.g.read(0x80018000, 0x8000)          # code; the first pages change at run time
        best = max(EXES, key=lambda f: sum(a == b for a, b in zip(
            ram, open(os.path.join(ROOT, 'work', 'source', 'disc', f), 'rb').read()[0x8800:0x10800])))
        return best

    def regs(self):
        r = self.g.cmd('g')
        while len(r) < 38 * 8 or r[0] in 'ST':     # skip stray stop replies
            r = self.g._recv_packet() if r[0] in 'ST' else self.g.cmd('g')
        return [struct.unpack('<I', bytes.fromhex(r[i * 8:i * 8 + 8].replace('x', '0')))[0]
                for i in range(len(r) // 8)]

    def setreg(self, n, v):
        assert self.g.cmd('P%x=%s' % (n, struct.pack('<I', v & 0xFFFFFFFF).hex())) == 'OK'

    def step_frame(self, buttons=0):
        """Continue to the next PadRead end; OR buttons into v0 there."""
        while True:
            self.g.s.sendall(b'$c#63')
            stop = self.g._recv_packet()
            r = self.regs()
            if r[37] == self.bp and (r[7] & 0xFFFF) == 0:     # port 1 only
                break
        if buttons:
            v0 = self.regs()[2]
            self.setreg(2, v0 | buttons)

    def press(self, names, frames=4):
        mask = 0
        for nm in names.split('+'):
            mask |= BTN[nm.lower()]
        for _ in range(frames):
            self.step_frame(mask)
        for _ in range(4):
            self.step_frame(0)

    def wait(self, frames):
        for _ in range(frames):
            self.step_frame(0)

    def grab(self, x, y, w, h):
        rows = max(1, SCRATCH_MAX // (w * 2))
        out = b''
        for yy in range(y, y + h, rows):
            out += self.grab1(x, yy, w, min(rows, y + h - yy))
        return out

    def grab1(self, x, y, w, h):
        """Read a VRAM rect (16-bit units) by running StoreImage from a stub.

        Runs from the entry of the game's own DrawSync (main loop, interrupts
        on); PadRead may run inside the VSync callback where DrawSync hangs."""
        ds = self.info['drawsync']
        self.g.cmd('Z0,%x,4' % ds)
        while True:
            self.g.s.sendall(b'$c#63')
            self.g._recv_packet()
            r = self.regs()
            # only from the main loop: interrupts enabled, game (not kernel) stack
            if r[37] == ds and (r[32] & 5) and r[29] >= 0x80010000:
                break
        self.g.cmd('z0,%x,4' % ds)
        regs = self.regs()
        size = w * h * 2
        need = 16 + 32 + size
        saved = self.g.read(SCRATCH, need)
        saved_stub = self.g.read(STUB, 32)
        rect = SCRATCH
        buf = SCRATCH + 16
        jal = lambda t: 0x0C000000 | ((t >> 2) & 0x3FFFFFF)
        stub = [jal(self.info['store']), 0, jal(self.info['drawsync']), 0x00002021, 0]  # move a0,zero
        self.g.write(STUB, struct.pack('<5I', *stub))
        self.g.write(rect, struct.pack('<4h', x, y, w, h))
        end = STUB + 16
        self.g.cmd('Z0,%x,4' % end)
        self.setreg(4, rect)
        self.setreg(5, buf)
        self.setreg(37, STUB)
        while True:
            self.g.s.sendall(b'$c#63')
            self.g._recv_packet()
            if self.regs()[37] == end:
                break
        self.g.cmd('z0,%x,4' % end)
        pix = self.g.read(buf, size)
        self.g.write(SCRATCH, saved)
        self.g.write(STUB, saved_stub)
        # restore all registers individually (gp regs, lo, hi, pc)
        for i in list(range(1, 32)) + [33, 34, 37]:
            self.setreg(i, regs[i])
        return pix

    def close(self):
        try:
            self.g.cmd('z0,%x,4' % self.bp)
        finally:
            self.g.close()


def write_png(path, w, h, pix16):
    rows = []
    for yy in range(h):
        r = bytearray()
        for p in struct.unpack_from('<%dH' % w, pix16, yy * w * 2):
            r += bytes(((p & 31) << 3, ((p >> 5) & 31) << 3, ((p >> 10) & 31) << 3))
        rows.append(b'\x00' + bytes(r))

    def chunk(t, data):
        c = struct.pack('>I', len(data)) + t + data
        return c + struct.pack('>I', zlib.crc32(t + data) & 0xFFFFFFFF)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress(b''.join(rows), 6)) + chunk(b'IEND', b'')
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    open(path, 'wb').write(png)


def displayed_rect(dbg):
    """Guess the front buffer: the game double-buffers at y=0 and y=240."""
    a = dbg.grab(0, 0, 320, 240)
    b = dbg.grab(0, 240, 320, 240)
    return a, b


def run(script):
    d = Dbg()
    try:
        print('exe', d.exe, {k: hex(v) for k, v in d.info.items() if v})
        for cmd in [c.strip() for c in script.split(';') if c.strip()]:
            p = cmd.split()
            if p[0] == 'press':
                d.press(p[1], int(p[2]) if len(p) > 2 else 4)
            elif p[0] == 'wait':
                d.wait(int(p[1]))
            elif p[0] == 'shot':
                if len(p) > 2:
                    x, y, w, h = (int(v, 0) for v in p[2:6])
                    write_png(p[1], w, h, d.grab(x, y, w, h))
                else:
                    a, b = displayed_rect(d)
                    write_png(p[1], 320, 240, a)
                    write_png(p[1].replace('.png', '_b.png'), 320, 240, b)
                print('shot', p[1])
            elif p[0] == 'vram':
                pix = b''
                for yy in range(0, 512, 64):
                    pix += d.grab(0, yy, 1024, 64)
                write_png(p[1], 1024, 512, pix)
                print('vram', p[1])
            elif p[0] == 'which':
                print(d.which())
            else:
                raise SystemExit('unknown command ' + cmd)
    finally:
        d.close()


if __name__ == '__main__':
    if sys.argv[1] == 'run':
        run(sys.argv[2])
    elif sys.argv[1] == 'info':
        for e in EXES:
            print(e, {k: (hex(v) if v else None) for k, v in exe_info(e).items()})
