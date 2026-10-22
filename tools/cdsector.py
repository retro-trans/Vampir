"""CD-ROM Mode 2 sector helpers: EDC and ECC (P/Q) generation.

Mode 2 Form 1: [sync 12][hdr 4][subhdr 8][data 2048][EDC 4][ECC 276]
Mode 2 Form 2: [sync 12][hdr 4][subhdr 8][data 2324][EDC 4]
For Mode 2 the ECC is computed with the 4 header bytes treated as zero.
"""
SYNC = b'\x00' + b'\xff' * 10 + b'\x00'


def _tables():
    ecc_f = [0] * 256
    ecc_b = [0] * 256
    edc = [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        ecc_f[i] = j & 0xFF
        ecc_b[i ^ j & 0xFF] = i
        e = i
        for _ in range(8):
            e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
        edc[i] = e
    return ecc_f, ecc_b, edc


ECC_F, ECC_B, EDC_T = _tables()


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_T[(e ^ b) & 0xFF]
    return e


def _ecc_pq(sec, major_count, minor_count, major_mult, minor_inc, dest):
    # sec: bytearray of the 2352-byte sector; computes over sec[12:] region
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = 0
        ecc_b = 0
        for _ in range(minor_count):
            temp = sec[12 + index]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= temp
            ecc_b ^= temp
            ecc_a = ECC_F[ecc_a]
        ecc_a = ECC_B[ECC_F[ecc_a] ^ ecc_b]
        sec[12 + dest + major] = ecc_a
        sec[12 + dest + major + major_count] = ecc_a ^ ecc_b


def ecc(sec):
    """Fill P and Q parity of a Mode 2 Form 1 sector (bytearray, in place)."""
    saved = bytes(sec[12:16])
    sec[12:16] = b'\x00\x00\x00\x00'
    _ecc_pq(sec, 86, 24, 2, 86, 2064)  # P parity -> sector offset 0x81C
    _ecc_pq(sec, 52, 43, 86, 88, 2064 + 172)  # Q -> 0x8C8
    sec[12:16] = saved


def bcd(n):
    return ((n // 10) << 4) | (n % 10)


def header(lba, mode=2):
    lba += 150
    return bytes((bcd(lba // 4500), bcd(lba // 75 % 60), bcd(lba % 75), mode))


def make_form1(lba, subheader, data):
    """Build a 2352-byte Mode 2 Form 1 sector. subheader: 4 bytes (file, chan, submode, coding)."""
    assert len(data) == 2048
    sec = bytearray(2352)
    sec[0:12] = SYNC
    sec[12:16] = header(lba)
    sec[16:20] = subheader
    sec[20:24] = subheader
    sec[24:2072] = data
    e = edc(sec[16:2072])
    sec[2072:2076] = e.to_bytes(4, 'little')
    ecc(sec)
    return bytes(sec)


def make_form2(lba, subheader, data):
    assert len(data) == 2324
    sec = bytearray(2352)
    sec[0:12] = SYNC
    sec[12:16] = header(lba)
    sec[16:20] = subheader
    sec[20:24] = subheader
    sec[24:2348] = data
    e = edc(sec[16:2348])
    sec[2348:2352] = e.to_bytes(4, 'little')
    return bytes(sec)


def self_test(path, lbas):
    ok = 0
    with open(path, 'rb') as f:
        for lba in lbas:
            f.seek(lba * 2352)
            raw = f.read(2352)
            sub = raw[16:20]
            if sub[2] & 0x20:
                rebuilt = make_form2(lba, sub, raw[24:2348])
            else:
                rebuilt = make_form1(lba, sub, raw[24:2072])
            if rebuilt == raw:
                ok += 1
            else:
                diff = [i for i in range(2352) if rebuilt[i] != raw[i]]
                print('lba', lba, 'mismatch at', diff[:8], len(diff))
    return ok


if __name__ == '__main__':
    import sys
    print(self_test(sys.argv[1], [int(x) for x in sys.argv[2:]]), 'sectors match')
