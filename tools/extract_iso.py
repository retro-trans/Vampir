"""Extract files from a PS1 MODE2/2352 BIN image (ISO9660) into a folder.

Usage: python tools/extract_iso.py "Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin" work/source/disc
Also writes <out>/_filelist.json with LBA/size/XA-form info per file.
"""
import json
import os
import struct
import sys

SECTOR = 2352


def read_sector(f, lba):
    f.seek(lba * SECTOR)
    raw = f.read(SECTOR)
    # Mode 2: sync(12) header(4) subheader(8); form 1 = 2048 bytes user data
    return raw


def user_data(raw):
    submode = raw[18]
    if submode & 0x20:  # form 2
        return raw[24:24 + 2324], 2
    return raw[24:24 + 2048], 1


def read_data(f, lba, size):
    out = bytearray()
    n = (size + 2047) // 2048
    for i in range(n):
        d, _ = user_data(read_sector(f, lba + i))
        out += d[:2048]
    return bytes(out[:size])


def parse_dir(f, lba, size, path, files):
    data = read_data(f, lba, size)
    pos = 0
    while pos < len(data):
        ln = data[pos]
        if ln == 0:
            pos = (pos // 2048 + 1) * 2048
            continue
        rec = data[pos:pos + ln]
        ext_lba = struct.unpack_from('<I', rec, 2)[0]
        ext_size = struct.unpack_from('<I', rec, 10)[0]
        flags = rec[25]
        nlen = rec[32]
        name = rec[33:33 + nlen]
        pos += ln
        if name in (b'\x00', b'\x01'):
            continue
        name = name.decode('ascii', 'replace').split(';')[0]
        full = path + '/' + name if path else name
        if flags & 2:
            parse_dir(f, ext_lba, ext_size, full, files)
        else:
            files.append({'path': full, 'lba': ext_lba, 'size': ext_size})


def main():
    img, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    files = []
    with open(img, 'rb') as f:
        pvd, _ = user_data(read_sector(f, 16))
        root = pvd[156:156 + 34]
        rlba = struct.unpack_from('<I', root, 2)[0]
        rsize = struct.unpack_from('<I', root, 10)[0]
        parse_dir(f, rlba, rsize, '', files)
        f.seek(0, 2)
        nsec = f.tell() // SECTOR
        files = [e for e in files if e['lba'] < nsec]  # DUMMY.DA points into the audio track
        for e in files:
            form = user_data(read_sector(f, e['lba']))[1]
            e['form'] = form
            dst = os.path.join(out, e['path'])
            os.makedirs(os.path.dirname(dst) or out, exist_ok=True)
            if form == 2:
                # XA/STR: dump raw sectors
                n = (e['size'] + 2047) // 2048
                f.seek(e['lba'] * SECTOR)
                with open(dst, 'wb') as o:
                    o.write(f.read(n * SECTOR))
            else:
                with open(dst, 'wb') as o:
                    o.write(read_data(f, e['lba'], e['size']))
    with open(os.path.join(out, '_filelist.json'), 'w') as o:
        json.dump(files, o, indent=1)
    for e in files:
        print(f"{e['lba']:7d} {e['size']:10d} form{e['form']} {e['path']}")


if __name__ == '__main__':
    main()
