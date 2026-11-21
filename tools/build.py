"""Build the English disc image.

    python tools/build.py [--test] [--version 0.1.0]
        -> work/output/<version>/Vampir (English v<version>).bin/.cue (+ Track 2 copy)

Inputs:
  work/source/disc/                 original files (tools/extract_iso.py)
  work/translation/en/rows/*.json   translated rows (tools/rows.py), field 'en'
  work/translation/en/dictionary.json   token dictionary (rebuilt from the rows)
--test fills every untranslated row with sample English so the engine can be
checked before the translation is complete.
"""
import argparse
import json
import os
import shutil
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font_atlas  # noqa: E402
import gfx  # noqa: E402
import stc_build  # noqa: E402
import vtext  # noqa: E402
import vwf  # noqa: E402
import talk  # noqa: E402
from build_disc import Disc  # noqa: E402
from strpatch import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'work', 'source', 'disc')
TR = os.path.join(ROOT, 'work', 'translation', 'en')
TRACK1 = os.path.join(ROOT, 'Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin')
TRACK2 = os.path.join(ROOT, 'Vampir - Kyuuketsuki Densetsu (Japan) (Track 2).bin')
OVL = 0x800CB800
OVL_LIMIT = 0x800EE800
OVL_TOP = 0x800ED800       # string pool end (a little below the STC at OVL_LIMIT)
EXE_BASE = 0x80010000
OVERLAYS = ['DC/OPN.BIN', 'DC/MCX.BIN', 'DC/END.BIN',
            'M0/C/M0A.BIN', 'M0/C/M0B.BIN', 'M0/C/EP0.BIN', 'M0/C/PR0.BIN',
            'M1/C/M1A.BIN', 'M1/C/M1B.BIN', 'M1/C/EP1.BIN', 'M1/C/PR1.BIN',
            'M2/C/M2A.BIN', 'M2/C/M2B.BIN', 'M2/C/EP2.BIN', 'M2/C/PR2.BIN']
STCS = ['M0/C/M0.STC', 'M1/C/M1.STC', 'M2/C/M2.STC']
# Strings the game joins with strcpy/strcat into fixed RAM buffers (overflow = hard crash).
# (buffer address, size, fixed bytes added by code, [alternatives for each part])
RUNTIME_BUFFERS = [
    # Nosferatu status, age: 2 full-width digits (4 bytes) + suffix; window state at 0x800A2A38
    (0x800A2A30, 8, 4, [['SLPS_019.32@E24']]),
    # Nosferatu status, type: Direct/Subord + Dhampir/Nosferatu; next buffer at 0x800A2A30
    (0x800A2A18, 24, 0, [['SLPS_019.32@DF8', 'SLPS_019.32@E00'], ['SLPS_019.32@E08', 'SLPS_019.32@E14']]),
]


def check_runtime_buffers(d, test):
    by_id = {r['id']: r for r in load_rows('SLPS_019.32')}
    for addr, size, extra, parts in RUNTIME_BUFFERS:
        worst = extra + 1 + sum(max(len(d.sjis(d.tokenize(english(by_id[i], test) or ''))) for i in alts)
                                for alts in parts)
        if worst > size:
            raise SystemExit('runtime buffer %08X overflows: %d > %d bytes (%s)' % (addr, worst, size, parts))


# overlays whose English labels do not fit in place and cannot use the string pool at the top of
# the overlay window (M1B.BIN alone reaches 0x800ED95E, past OVL_TOP): their pointer-referenced
# strings are put once in the resident EXE string pool and the overlay's references repointed
# there; code-referenced strings must fit in place
RESIDENT_TEXT = ['M0/C/M0B.BIN', 'M1/C/M1B.BIN', 'M2/C/M2B.BIN']
SAMPLES = [
    "The village of Medvekia lies at the foot of the castle.",
    "I'm counting on you, Christopher.",
    "Is there some reason you came all this way?",
    "Good evening. What brings you out so late?",
    "Hunters have been seen near the church at night.",
    "Don't worry. Everything will be fine, I promise.",
    "We vampires must not be seen by human eyes.",
    "Excuse me, but who exactly are you?",
]


def rows_file(name):
    return os.path.join(TR, 'rows', name.replace('/', '_') + '.json')


def load_rows(name):
    p = rows_file(name)
    if not os.path.exists(p):
        return []
    return json.load(open(p, encoding='utf8'))


def english(row, test):
    t = row.get('en') or ''
    if t or row.get('done'):
        return t                          # '' = deliberately empty (e.g. an honorific after a name)
    if test:
        if row.get('stc', 1) % 2 == 0:
            return 'Hmm...'
        return SAMPLES[zlib.crc32(row['id'].encode()) % len(SAMPLES)]
    return None


def all_lines(test):
    lines = []
    for f in sorted(os.listdir(os.path.join(TR, 'rows'))) if os.path.isdir(os.path.join(TR, 'rows')) else []:
        if f.endswith('.json') and not f.endswith('.en.json'):
            # M2.STC (London) is the tightest file (original 0x337DA of 0x34000): weight its text
            # in the token dictionary so it compresses best
            weight = 3 if f.startswith('M2_C_M2.STC') else 1
            for r in json.load(open(os.path.join(TR, 'rows', f), encoding='utf8')):
                t = english(r, test)
                if t:
                    lines += [t] * weight
    return lines + SAMPLES


# name entry (OPN.BIN): 90 cells = left block 9x5 then right block 9x5 (row-major), the last
# two cells are the confirm button, then the 'no name entered' message
NAME_GRID = ('ABCDE' 'FGHIJ' 'KLMNO' 'PQRST' 'UVWXY' "Z.,'-" '01234' '56789' '!?&  '
             'abcde' 'fghij' 'klmno' 'pqrst' 'uvwxy' 'zéèêà' 'âäöüç' 'ñôûïÉ' '   ') + 'OK'
GRID_ID = 'OPN.BIN@12B8'
LETTER_ROWS = {'OPN.BIN@13A8', 'OPN.BIN@13B8',        # default player names: editable letters
               # memory-card file title pieces: must stay full-width Shift-JIS (BIOS + title parser)
               'MCX.BIN@9B4', 'MCX.BIN@9C8', 'MCX.BIN@9D0', 'MCX.BIN@9E0', 'MCX.BIN@9EC', 'MCX.BIN@9F0',
               'MCX.BIN@24', 'MCX.BIN@1C', 'MCX.BIN@34', 'MCX.BIN@30'}   # Start End Morning Evening
GRID_MESSAGE = 'Enter a name.'

# Memory-card save title (DC/MCX.BIN 0x800CEE94): built with strcat in a 64-byte stack buffer
# (31 full-width letters + NUL; the saved registers follow, so a longer title crashes the save)
# and parsed back on load at the 0x8140 separators: [Vampir] [name <= 8] [STAGEn] [day part].
# English: "Vampir Chris STAGE1 D12 Morn" (worst case 31 letters).  The slot list's day field
# (16 bytes) starts with a full-width D instead of an empty string; the title takes the
# finished day field (vwf.py MCX_DAY) instead of appending digits/suffix/time itself.
JAL_STRCAT = 0x0C000000 | (0x8006109C >> 2 & 0x3FFFFFF)


def mcx_code(d, syms):
    dd = letters_sjis(d, 'D')
    imm = dd[0] | dd[1] << 8                          # 'D' then NUL in the low half of a word
    jal = lambda t: struct.pack('<I', 0x0C000000 | (t >> 2 & 0x3FFFFFF))
    nop = bytes(4)
    p = [(0x800CC1C4, bytes(1)),                     # '(' -> empty string
         (0x800CEF20, nop),                           # title: no slot digit
         (0x800CF1E0, struct.pack('<I', 0x34030000 | imm)),   # ori v1, zero, 'D'
         (0x800CF1E4, nop),
         (0x800CF1EC, struct.pack('<I', 0xAC430000)),         # sw v1, 0(v0)
         (0x800CF224, nop), (0x800CF2AC, nop),        # title: tens / units digit
         (0x800CF314, nop), (0x800CF374, nop),        # title: suffix / time word
         (0x800CF3BC, jal(syms['MCX_DAY']))]          # day field time word, then title += field
    src = open(os.path.join(SRC, 'DC', 'MCX.BIN'), 'rb').read()
    word = lambda a: struct.unpack_from('<I', src, a - OVL)[0]
    for a in (0x800CEF20, 0x800CF224, 0x800CF2AC, 0x800CF314, 0x800CF374, 0x800CF3BC):
        assert word(a) == JAL_STRCAT, hex(a)
    assert src[0x800CC1C4 - OVL:0x800CC1C7 - OVL] == bytes((0x81, 0x69, 0))        # '('
    assert word(0x800CF1E4) == 0x9063BFFC and word(0x800CF1EC) == 0xA0430000      # lbu / sb
    return p


SJIS_SPACE = bytes((0x81, 0x40))


FAILED = []


def letters_sjis(d, text):
    return b''.join(SJIS_SPACE if c == ' ' else d.codes[d.char_id[c]] for c in text)


def drain_label_x(name, data, d, test):
    """Drain screen (?B.BIN): the eight labels are encoded into 12-byte buffers at sp+0x10+12i
    (pointer-table order) and drawn left-aligned at constant x (addiu v0,zero,x; sh v0,-0x9E0(v1)),
    each Japanese label ending where its number column begins.  Right-align the English labels
    to the same end, from their pixel width.  Returns [(file offset, new instruction)]."""
    rows = [r for r in load_rows(name) if any(ref[0] == 'ptr' for ref in r.get('refs', []))]
    base_ptr = min(ref[1] for r in rows for ref in r['refs'] if ref[0] == 'ptr')
    words = struct.unpack_from('<%dI' % (len(data) // 4), data)
    out = []
    for r in rows:
        t = english(r, test)
        if not t:
            continue
        toks = d.tokenize(t)
        assert len(toks) <= 7, (name, t, len(toks))           # 12-byte nibble buffer
        i = (next(ref[1] for ref in r['refs'] if ref[0] == 'ptr') - base_ptr) // 4
        hits = []
        for k, w in enumerate(words):
            if w != 0x27A50000 | (0x10 + 12 * i):              # addiu a1, sp, 0x10+12i
                continue
            for j in range(k + 1, min(k + 20, len(words) - 3)):
                if words[j] >> 16 == 0x2402 and 0xA462F620 in words[j + 1:j + 4]:
                    hits.append(j)
                    break
        assert len(hits) == 1, (name, i, hits)
        j = hits[0]
        old = struct.unpack('<h', struct.pack('<H', words[j] & 0xFFFF))[0]
        right = old + 12 * len(r['jp'])                         # where the Japanese label ended
        new = right - sum(d.width(tok) for tok in toks)
        out.append((4 * j, struct.pack('<I', 0x24020000 | (new & 0xFFFF))))
    return out


def build_strings(name, data, base, test, d, pool=None, limit=None, resident=None):
    """Relocate translated strings of an overlay / EXE body; returns patched bytes.
    resident: {english: address} of strings already placed in the EXE (RESIDENT_TEXT)."""
    img = Image(data, base, pool=pool, limit=limit)
    n = 0
    if test and name == 'SLPS_019.32':
        return img, 0                    # EXE strings include SJIS tables: no samples there
    rows = load_rows(name)
    rows.sort(key=lambda r: not any(x[0] == 'code' for x in r.get('refs', [])))   # code refs first
    for r in rows:
        if 'off' not in r:
            continue
        if r['id'] == GRID_ID:
            b = letters_sjis(d, NAME_GRID) + d.sjis(d.tokenize(GRID_MESSAGE))
            assert len(b) <= r['size'], len(b)
            o = r['off']
            img.data[o:o + r['size'] + 1] = b.ljust(r['size'] + 1, b'\x00')
            n += 1
            continue
        t = english(r, test)
        if t is None:
            continue
        if 'field' in r:                  # fixed-size record read by index (rows.py TABLES)
            b = d.sjis(d.tokenize(t))
            if len(b) >= r['field']:
                FAILED.append((r['id'], t, len(b), r['field'] - 1))
                continue
            o = r['off']
            img.data[o:o + r['field']] = b + bytes(r['field'] - len(b))
            n += 1
            continue
        if r['id'] in LETTER_ROWS:
            b = letters_sjis(d, t)
        else:
            b = d.sjis(d.tokenize(t))
        if resident and t in resident:
            try:
                img.repoint(base + r['off'], resident[t], r['refs'])
                n += 1
            except ValueError:
                FAILED.append((r['id'], t, len(b), r.get('slot', r['size'])))
            continue
        try:
            img.relocate(base + r['off'], b, r['refs'], old_size=r.get('slot', r['size']))
        except ValueError:
            FAILED.append((r['id'], t, len(b), r.get('slot', r['size'])))
            continue
        n += 1
    return img, n


def build(version, test):
    out_dir = os.path.join(ROOT, 'work', 'output', version)
    os.makedirs(out_dir, exist_ok=True)
    # dictionary
    lines = all_lines(test)
    d = vtext.Dictionary.build(lines)
    check_runtime_buffers(d, test)
    os.makedirs(TR, exist_ok=True)
    d.save(os.path.join(out_dir, 'dictionary.json'))
    print('tokens', len(d.tokens), 'from', len(lines), 'lines')
    # font
    glyphs, tex, th4, letters_blob = font_atlas.make()
    files = {'CM/FT1.TH4': th4, 'CM/FT2.TH4': th4, 'CM/FT3.TH4': th4}
    files.update(gfx.patch())             # text baked into TIM graphics
    # EXE
    exe = bytearray(open(os.path.join(SRC, 'SLPS_019.32'), 'rb').read())
    body = exe[0x800:]
    toks = [d.letter_ids(t) for t in range(len(d.tokens))]
    cluts = [font_atlas.clut_id(a) for a in range(8)]
    code, syms, patches = vwf.build(toks, cluts, letters_blob)
    ovl_code = {'DC/MCX.BIN': mcx_code(d, syms)}
    for a, b in patches:
        o = a - EXE_BASE
        body[o:o + len(b)] = b
    wpad = bytes(min(255, d.width(t)) if t < len(d.tokens) else 0 for t in range(vwf.NGLYPH))
    o = vwf.WIDTHS - EXE_BASE
    body[o:o + vwf.NGLYPH] = wpad
    ext = vwf.BASE + len(code)
    body = body[:vwf.BASE - EXE_BASE] + code
    img, n = build_strings('SLPS_019.32', bytes(body), EXE_BASE, test, d, pool=ext, limit=vwf.LIMIT)
    resident = {}
    for name in RESIDENT_TEXT:
        for r in load_rows(name):
            t = english(r, test)
            if t is None or 'off' not in r or t in resident:
                continue
            if any(ref[0] == 'code' for ref in r['refs']):
                continue                  # code-referenced (title): stays in place below
            resident[t] = img.alloc(d.sjis(d.tokenize(t)) + bytes(2))
    body = bytes(img.data)
    body += bytes((-len(body)) % 0x800)
    hdr = bytearray(exe[:0x800])
    struct.pack_into('<I', hdr, 0x1C, len(body))
    files['SLPS_019.32'] = bytes(hdr) + body
    print('EXE', hex(len(body)), 'hooks', len(code), 'bytes, strings', n, 'end', hex(EXE_BASE + len(body)))
    # overlays
    for name in OVERLAYS:
        data = open(os.path.join(SRC, name), 'rb').read()
        # Relocated strings must not land right after the file: that memory is the overlay's
        # BSS (the EXE uses it too, e.g. 0x800D9DB0 with M0A loaded). They go at the top of the
        # overlay window instead, just below the resident STC; the gap is loaded as zeros.
        probe = (OVL + len(data) + 0xF) & ~0xF
        failed = len(FAILED)
        img, n = build_strings(name, data, OVL, test, d, pool=probe, limit=OVL_LIMIT, resident=resident)
        used = img.pool - probe
        if len(img.data) > len(data):
            del FAILED[failed:]
            top = (OVL_TOP - used) & ~0xF
            assert top >= OVL + len(data), (name, hex(top))
            img, n = build_strings(name, data, OVL, test, d, pool=top, limit=OVL_TOP, resident=resident)
            assert OVL + len(img.data) <= OVL_TOP
        for a, b in ovl_code.get(name, []):
            img.data[a - OVL:a - OVL + len(b)] = b
            n += 1
        if name in RESIDENT_TEXT:
            for o, b in drain_label_x(name, data, d, test):
                img.data[o:o + 4] = b
        if n:
            files[name] = bytes(img.data)
            print(name, 'strings', n, 'size', hex(len(data)), '->', hex(len(img.data)))
    # STC
    for name in STCS:
        orig = open(os.path.join(SRC, name), 'rb').read()
        rows = load_rows(name)
        n_str = struct.unpack_from('<I', orig, struct.unpack_from('<I', orig, 8)[0])[0] // 8
        strings = [None] * n_str
        names, jobs = {}, {}
        for r in rows:
            t = english(r, test)
            if 'stc' in r:
                strings[r['stc']] = t
            elif 'name' in r:
                names[r['name']] = r.get('en') or None
            elif 'job' in r:
                jobs[r['job']] = r.get('en') or None
        nrec = struct.unpack_from('<I', orig, 0x0C)[0]
        if test:
            strings = [s if s is not None else (SAMPLES[k % len(SAMPLES)] if k % 2 else 'Hmm...') for k, s in enumerate(strings)]
            names = {i: names.get(i) or 'Villager %d' % i for i in range(nrec)}
            jobs = {i: jobs.get(i) or 'Farmer' for i in range(nrec)}
        if None in strings:
            print(name, 'untranslated strings:', strings.count(None), '- shown as [#k]')
            strings = [t if t is not None else '[#%d]' % k for k, t in enumerate(strings)]
        nrec = struct.unpack_from('<I', orig, 0x0C)[0]
        for i in range(nrec):
            names.setdefault(i, None)
            jobs.setdefault(i, None)
        names = {i: (v if v is not None else 'N%d' % i) for i, v in names.items()}
        jobs = {i: (v if v is not None else '-') for i, v in jobs.items()}
        # per-message variants: a copy of the string at a new index, repointed in the SQC script
        ch = os.path.basename(name)[:2]
        sqc_name = name.replace('.STC', '.SQC')
        sqc = open(os.path.join(SRC, sqc_name), 'rb').read()
        n0 = len(strings)
        nvar = 0
        shared = {}                       # identical variant texts share one string
        # variants keyed at a single reference first, then message-wide ones (they repoint the
        # remaining references of that string in the message)
        allv = [(r, v) for r in rows for v in r.get('variants') or [] if 'stc' in r and v.get('en') is not None]
        allv.sort(key=lambda rv: 'ref' not in rv[1])
        for r, v in allv:
            if v['en'] not in shared:
                strings.append(v['en'])
                shared[v['en']] = len(strings) - 1
            if 'ref' in v:
                sqc = talk.patch_run(sqc, int(v['ref']), r['stc'], shared[v['en']], n0, single=True)
            else:
                sqc = talk.patch_run(sqc, int(v['msg']), r['stc'], shared[v['en']], n0)
            nvar += 1
        if nvar:
            files[sqc_name] = sqc
            print(sqc_name, 'variants', nvar)
        data, tab = stc_build.build(orig, d, strings, [names[i] for i in range(nrec)],
                                    [jobs[i] for i in range(nrec)])
        stc_build.verify(data, d, strings)
        files[name] = data
        print(name, hex(len(orig)), '->', hex(len(data)), 'P', tab.P)
    for f in FAILED:
        print('NOT INSERTED (needs <= %d bytes, has %d): %s %r' % (f[3], f[2], f[0], f[1]))
    # disc
    stem = 'Vampir (English v%s)' % version
    t1 = os.path.join(out_dir, stem + ' (Track 1).bin')
    disc = Disc.open_copy(TRACK1, t1)
    before = disc.nsectors
    # Files that may grow get fixed places at the end of the image, in a fixed order and with a
    # fixed capacity: their LBAs then stay the same from build to build (the game caches file
    # positions at boot, so save states survive rebuilds).
    reserve = [('SLPS_019.32', 0xBC000)] + [(n, 0x23000) for n in OVERLAYS] + [(n, 0x34000) for n in STCS]
    for name, cap in reserve:
        data = files.pop(name, None)
        if data is None:
            data = disc.read_file(name)
        disc.replace(name, data, reserve=cap // 2048)
    for name, data in files.items():
        moved = disc.replace(name, data)
        if moved:
            print('moved', name)
    grow = disc.nsectors - before
    if grow:
        e = disc.entries['DUMMY.DA']
        e.lba += grow                     # the audio track follows the grown data track
        disc._write_dir_record(e)
    disc.close()
    t2 = os.path.join(out_dir, stem + ' (Track 2).bin')
    if not os.path.exists(t2) or os.path.getsize(t2) != os.path.getsize(TRACK2):
        shutil.copyfile(TRACK2, t2)
    cue = ('FILE "%s (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n'
           'FILE "%s (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n    INDEX 00 00:00:00\n    INDEX 01 00:02:00\n'
           % (stem, stem))
    open(os.path.join(out_dir, stem + '.cue'), 'w').write(cue)
    print('disc grew by', grow, 'sectors ->', os.path.join(out_dir, stem + '.cue'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--test', action='store_true')
    ap.add_argument('--version', default='0.1.0')
    a = ap.parse_args()
    build(a.version, a.test)


if __name__ == '__main__':
    main()
