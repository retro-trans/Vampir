"""Patch files inside a copy of the Riot Stars BIN (Mode 2 Form 1, ISO9660).

Library use:
    d = Disc.open_copy(src_bin, out_bin)
    d.replace('KOUSEI.EXE', data)      # in place if it fits, else appended at the end
    d.close()                          # writes PVD volume size if the image grew

Every written sector gets a correct header, subheader, EDC and ECC.
Unchanged sectors are never touched.
"""
import os
import shutil
import struct

from cdsector import make_form1

SECTOR = 2352


class Entry:
    def __init__(self, path, lba, size, rec_lba, rec_off):
        self.path, self.lba, self.size = path, lba, size
        self.rec_lba, self.rec_off = rec_lba, rec_off  # where the directory record lives


class Disc:
    def __init__(self, path, mode='r+b'):
        self.path = path
        self.f = open(path, mode)
        self.f.seek(0, 2)
        self.nsectors = self.f.tell() // SECTOR
        self.grew = False
        self.entries = {}
        pvd = self.data(16)
        root = pvd[156:190]
        self._walk(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0], '')

    @classmethod
    def open_copy(cls, src, dst):
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        shutil.copyfile(src, dst)
        return cls(dst)

    def raw(self, lba):
        self.f.seek(lba * SECTOR)
        return self.f.read(SECTOR)

    def data(self, lba):
        return self.raw(lba)[24:24 + 2048]

    def _walk(self, lba, size, path):
        for s in range((size + 2047) // 2048):
            sec = self.data(lba + s)
            pos = 0
            while pos < 2048:
                ln = sec[pos]
                if ln == 0:
                    break
                rec = sec[pos:pos + ln]
                name = rec[33:33 + rec[32]]
                if name not in (b'\x00', b'\x01'):
                    name = name.decode('ascii').split(';')[0]
                    full = path + '/' + name if path else name
                    elba = struct.unpack_from('<I', rec, 2)[0]
                    esize = struct.unpack_from('<I', rec, 10)[0]
                    if rec[25] & 2:
                        self._walk(elba, esize, full)
                    else:
                        self.entries[full.upper()] = Entry(full, elba, esize, lba + s, pos)
                pos += ln

    def read_file(self, path):
        e = self.entries[path.upper()]
        out = bytearray()
        for i in range((e.size + 2047) // 2048):
            out += self.data(e.lba + i)
        return bytes(out[:e.size])

    def _write_sector(self, lba, sub, payload):
        payload = payload.ljust(2048, b'\x00')
        self.f.seek(lba * SECTOR)
        self.f.write(make_form1(lba, sub, payload))

    def _write_dir_record(self, e):
        raw = bytearray(self.raw(e.rec_lba))
        sub = bytes(raw[16:20])
        d = raw[24:24 + 2048]
        o = e.rec_off
        d[o + 2:o + 10] = struct.pack('<I', e.lba) + struct.pack('>I', e.lba)
        d[o + 10:o + 18] = struct.pack('<I', e.size) + struct.pack('>I', e.size)
        self._write_sector(e.rec_lba, sub, bytes(d))

    def replace(self, path, data, reserve=None):
        """reserve=n: always move the file to the end of the image into n sectors (zero
        filled), so its position does not depend on its size (stable LBAs between builds)."""
        e = self.entries[path.upper()]
        old_n = (e.size + 2047) // 2048
        new_n = (len(data) + 2047) // 2048
        subs = [self.raw(e.lba + i)[16:20] for i in range(old_n)]
        if reserve is not None:
            assert new_n <= reserve, (path, new_n, reserve)
            lba = self.nsectors
            self.nsectors += reserve
            self.grew = True
            for i in range(new_n, reserve):
                self._write_sector(lba + i, bytes((0, 0, 0x08, 0)), b'')
        elif new_n <= old_n:
            lba = e.lba
        else:
            lba = self.nsectors          # append after the current end of the image
            self.nsectors += new_n
            self.grew = True
        for i in range(new_n):
            if i < old_n - 1:
                sub = subs[i]
            else:
                sub = bytes((0, 0, 0x08, 0))
            if i == new_n - 1:
                sub = bytes((sub[0], sub[1], 0x89, sub[3]))   # data | EOR | EOF
            self._write_sector(lba + i, sub, data[i * 2048:(i + 1) * 2048])
        moved = lba != e.lba
        e.lba, e.size = lba, len(data)
        self._write_dir_record(e)
        return moved

    def write_file_sectors(self, path, sectors):
        """Rewrite single Form 1 sectors of a file in place, keeping each one's subheader.
        sectors: {sector index in the file: 2048 bytes}.  Other sectors (e.g. XA audio
        interleaved in STR movies) are untouched."""
        e = self.entries[path.upper()]
        for i, payload in sectors.items():
            raw = self.raw(e.lba + i)
            assert not raw[18] & 0x20, (path, i, 'form 2 sector')
            self._write_sector(e.lba + i, bytes(raw[16:20]), payload)

    def close(self):
        if self.grew:
            raw = bytearray(self.raw(16))
            d = raw[24:24 + 2048]
            d[80:88] = struct.pack('<I', self.nsectors) + struct.pack('>I', self.nsectors)
            self._write_sector(16, bytes(raw[16:20]), bytes(d))
        self.f.close()
