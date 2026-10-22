"""Relocate translated strings inside a memory image (overlay or EXE body).

    img = Image(data, base)
    img.relocate(old_addr, new_bytes, refs)    # refs from tools/extract_text.py
    img.data                                    # patched bytes (may have grown)

New strings are appended after `pool` (default: end of the image), 4-byte aligned.
Data pointers ('ptr') are rewritten; code references ('code', the address of the
lui's partner instruction) are rewritten as lui + low half when the lui register
feeds only this instruction, otherwise only the low half when the high half does
not change. If neither is possible the string is written in place when it fits.
"""
import struct


def _w(d, a):
    return struct.unpack_from('<I', d, a)[0]


def hi_lo(addr):
    lo = addr & 0xFFFF
    return ((addr + 0x8000) >> 16) & 0xFFFF, lo


class Image:
    def __init__(self, data, base, pool=None, limit=None):
        self.data = bytearray(data)
        self.base = base
        self.pool = base + len(self.data) if pool is None else pool
        self.limit = limit
        self.log = []

    def off(self, addr):
        return addr - self.base

    def word(self, addr):
        return _w(self.data, self.off(addr))

    def put_word(self, addr, v):
        struct.pack_into('<I', self.data, self.off(addr), v & 0xFFFFFFFF)

    def alloc(self, b):
        self.pool = (self.pool + 3) & ~3
        a = self.pool
        end = self.off(a + len(b))
        if self.limit is not None and a + len(b) > self.limit:
            raise ValueError('string pool overflow at %08X' % a)
        if end > len(self.data):
            self.data += bytes(end - len(self.data))
        self.data[self.off(a):end] = b
        self.pool = a + len(b)
        return a

    def _find_lui(self, at):
        """lui feeding the instruction at `at`; returns (lui_addr, rt) or None."""
        y = self.word(at)
        rs = (y >> 21) & 31
        for k in range(1, 24):
            a = at - 4 * k
            if a < self.base:
                break
            x = self.word(a)
            if x >> 26 == 0x0F and (x >> 16) & 31 == rs:
                return a, rs
        return None

    def _uses(self, lui_addr, rt, limit=40):
        """Instructions after the lui that read rt as a base/source, until rt is redefined."""
        uses = []
        a = lui_addr + 4
        end = self.base + len(self.data)
        for _ in range(limit):
            if a >= end:
                break
            x = self.word(a)
            op = x >> 26
            rs, rtt, rd = (x >> 21) & 31, (x >> 16) & 31, (x >> 11) & 31
            reads = False
            if op == 0:
                reads = rs == rt or rtt == rt
                writes = rd == rt
            elif op in (0x02, 0x03):
                writes = False
            elif op in (0x04, 0x05):
                reads = rs == rt or rtt == rt
                writes = False
            elif op in (0x01, 0x06, 0x07):
                reads = rs == rt
                writes = False
            elif op >= 0x28:                     # stores
                reads = rs == rt or rtt == rt
                writes = False
            else:                                # immediates and loads
                reads = rs == rt
                writes = rtt == rt
            if reads:
                uses.append(a)
            if writes:
                break
            a += 4
        return uses

    def patch_code_ref(self, at, new):
        f = self._find_lui(at)
        if not f:
            return False
        lui, rt = f
        hi, lo = hi_lo(new)
        old_hi = self.word(lui) & 0xFFFF
        y = self.word(at)
        if hi == old_hi:
            self.put_word(at, (y & 0xFFFF0000) | lo)
            return True
        uses = self._uses(lui, rt)
        if uses == [at]:
            self.put_word(lui, (self.word(lui) & 0xFFFF0000) | hi)
            self.put_word(at, (y & 0xFFFF0000) | lo)
            return True
        return False

    def relocate(self, old, new_bytes, refs, old_size=None):
        """Point every reference of the string at `old` to new_bytes (NUL added)."""
        b = new_bytes + b'\0\0'
        codes = [r[1] for r in refs if r[0] == 'code']
        ptrs = [r[1] for r in refs if r[0] == 'ptr']
        fits = old_size is not None and len(new_bytes) + 1 <= old_size + 1
        if fits and codes:
            # in place: no reference changes at all
            o = self.off(old)
            self.data[o:o + old_size + 1] = new_bytes.ljust(old_size + 1, b'\0')
            self.log.append(('inplace', old))
            return old
        new = self.alloc(b)
        ok = all(self._can_patch(c, new) for c in codes)
        if not ok:
            if fits:
                o = self.off(old)
                self.data[o:o + old_size + 1] = new_bytes.ljust(old_size + 1, b'\0')
                self.log.append(('inplace', old))
                return old
            raise ValueError('cannot repoint code reference to %08X' % old)
        for c in codes:
            self.patch_code_ref(c, new)
        for p in ptrs:
            self.put_word(p, new)
        self.log.append(('moved', old, new))
        return new

    def _can_patch(self, at, new):
        f = self._find_lui(at)
        if not f:
            return False
        lui, rt = f
        hi, _ = hi_lo(new)
        if hi == self.word(lui) & 0xFFFF:
            return True
        return self._uses(lui, rt) == [at]
