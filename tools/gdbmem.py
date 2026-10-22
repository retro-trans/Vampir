"""Minimal GDB remote-protocol client for DuckStation's GDB server (port 2346, RS_GDB_PORT; 2345 is often taken by other emulators).

    python tools/gdbmem.py read <addr> <len> [out.bin]   hex dump or save RAM
    python tools/gdbmem.py dumpram <out.bin>             2 MiB main RAM
    python tools/gdbmem.py regs
    python tools/gdbmem.py which                         which EXE is in RAM
Enable [Debug] EnableGDBServer in settings.ini. Reading pauses the CPU
briefly; the client detaches ('c') afterwards so the game keeps running.
"""
import socket
import sys

PORT = int(__import__('os').environ.get('RS_GDB_PORT', '2346'))   # work/emulator settings.ini GDBServerPort


class Gdb:
    def __init__(self, port=PORT):
        self.s = socket.create_connection(('127.0.0.1', port), timeout=10)
        self.buf = b''

    def _recv_packet(self):
        while True:
            while b'#' not in self.buf or len(self.buf) < self.buf.index(b'#') + 3:
                self.buf += self.s.recv(65536)
            i = self.buf.find(b'$')
            j = self.buf.index(b'#', i)
            pkt = self.buf[i + 1:j]
            self.buf = self.buf[j + 3:]
            self.s.sendall(b'+')
            return pkt.decode('latin1')

    def cmd(self, c):
        csum = sum(c.encode()) & 0xFF
        self.s.sendall(('$%s#%02x' % (c, csum)).encode())
        r = self._recv_packet()
        while c[0] in 'mMPgZz' and len(r) == 3 and r[0] in 'ST' and c != '?':
            r = self._recv_packet()          # stray stop reply from an earlier continue
        return r

    def read(self, addr, n):
        out = bytearray()
        while n > 0:
            k = min(n, 0x800)
            r = self.cmd('m%x,%x' % (addr, k))
            if r.startswith('E'):
                raise IOError('read error at %08x: %s' % (addr, r))
            out += bytes.fromhex(r)
            addr += k
            n -= k
        return bytes(out)

    def write(self, addr, data):
        for i in range(0, len(data), 0x400):
            chunk = data[i:i + 0x400]
            r = self.cmd('M%x,%x:%s' % (addr + i, len(chunk), chunk.hex()))
            if r != 'OK':
                raise IOError(r)

    def close(self):
        try:
            self.s.sendall(b'$c#63')
        finally:
            self.s.close()


def which(g):
    import struct
    ram = g.read(0x80018000, 0x8000)
    best = []
    for f in ['SLPS_008.29', 'MAIN1.EXE', 'KOUSEI.EXE', 'CASINO.EXE', 'KEIBA.EXE']:
        d = open('work/source/disc/' + f, 'rb').read()[0x8800:0x10800]
        same = sum(a == b for a, b in zip(ram, d))
        best.append((same, f))
    best.sort(reverse=True)
    return best


def main():
    g = Gdb()
    try:
        op = sys.argv[1]
        if op == 'read':
            a, n = int(sys.argv[2], 16), int(sys.argv[3], 16)
            d = g.read(a, n)
            if len(sys.argv) > 4:
                open(sys.argv[4], 'wb').write(d)
            else:
                for i in range(0, len(d), 16):
                    print('%08X  %s' % (a + i, d[i:i + 16].hex(' ')))
        elif op == 'dumpram':
            open(sys.argv[2], 'wb').write(g.read(0x80000000, 0x200000))
        elif op == 'regs':
            print(g.cmd('g'))
        elif op == 'which':
            for s, f in which(g):
                print(s, f)
    finally:
        g.close()


if __name__ == '__main__':
    main()
