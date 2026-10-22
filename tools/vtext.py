"""English text encoding for the VWF hooks.

The game's "glyph" ids become *tokens*: one or more letters drawn together. Ids
0x00-0x9F are single letters (same number as the font letter id, see
tools/font_atlas.py); ids 0xA0.. are multi-letter tokens learned from the English
script (BPE merges inside words, never across a space). Spaces are the single
token 0x20, so the layout hook can wrap at word boundaries.

Each token also has a 2-byte code for the game's runtime string encoder (it looks
2-byte "characters" up in the chapter table): single letters use their full-width
Shift-JIS code (player names, numbers), other tokens the user-defined area F040+.

    d = Dictionary.build(corpus_lines)      # or Dictionary.load(path)
    ids = d.tokenize('Hello there.')
    sjis = d.sjis(ids)                      # bytes for overlay / EXE strings
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import font_atlas  # noqa: E402

NGLYPH = 1323            # width table / table search limit in the EXE
FIRST_MULTI = 0xA0
SPACE = 0x20
# characters normalised before encoding
NORMAL = {' ': ' ', ' ': ' ', '‘': '‘', '’': '’', '“': '“', '”': '”',
          '—': '—', '–': '–', '…': '…'}


def fullwidth_sjis(ch):
    if ch == ' ':
        return b'\x81\x40'
    if '!' <= ch <= '~':
        try:
            return chr(ord(ch) + 0xFEE0).encode('cp932')
        except UnicodeEncodeError:
            return None
    try:
        b = ch.encode('cp932')
        return b if len(b) == 2 else None
    except UnicodeEncodeError:
        return None


def user_code(n):
    """n-th code of the Shift-JIS user-defined area F040-F9FC (skipping 7F)."""
    lead, trail = divmod(n, 188)
    t = 0x40 + trail
    if t >= 0x7F:
        t += 1
    return bytes([0xF0 + lead, t])


class Dictionary:
    def __init__(self, multi):
        self.letters = font_atlas.letters()          # id -> char
        self.char_id = {c: i for i, c in self.letters.items()}
        adv = font_atlas.advances()
        self.adv = adv
        self.tokens = [None] * FIRST_MULTI
        for i, c in self.letters.items():
            self.tokens[i] = c
        self.tokens += list(multi)
        if len(self.tokens) > NGLYPH:
            raise ValueError('too many tokens: %d' % len(self.tokens))
        self.index = {t: i for i, t in enumerate(self.tokens) if t is not None}
        self.maxlen = max(len(t) for t in self.tokens if t)
        self.codes = {}
        used = set()
        n = 0
        for i, t in enumerate(self.tokens):
            if t is None:
                continue
            c = fullwidth_sjis(t) if len(t) == 1 else None
            if c is None or c in used:
                c = user_code(n)
                n += 1
            used.add(c)
            self.codes[i] = c
        self.by_code = {c: i for i, c in self.codes.items()}

    # ------------------------------------------------------------------ metrics
    def width(self, tid):
        t = self.tokens[tid]
        return sum(self.adv[c] for c in t) if t else 0

    def letter_ids(self, tid):
        t = self.tokens[tid]
        return [self.char_id[c] for c in t] if t else []

    def text_width(self, text):
        return sum(self.adv.get(c, 0) for c in normalize(text))

    # ------------------------------------------------------------------ encoding
    def tokenize(self, text, cost=None):
        """Fewest-cost token sequence for text (DP); cost(tid) defaults to 1."""
        s = normalize(text)
        bad = [c for c in s if c not in self.char_id]
        if bad:
            raise ValueError('no glyph for %r in %r' % (''.join(sorted(set(bad))), text))
        n = len(s)
        best = [0] + [None] * n
        back = [None] * (n + 1)
        for i in range(n):
            if best[i] is None:
                continue
            for k in range(1, min(self.maxlen, n - i) + 1):
                tid = self.index.get(s[i:i + k])
                if tid is None:
                    continue
                c = best[i] + (cost(tid) if cost else 1)
                if best[i + k] is None or c < best[i + k]:
                    best[i + k] = c
                    back[i + k] = (i, tid)
        out = []
        i = n
        while i:
            j, tid = back[i]
            out.append(tid)
            i = j
        return out[::-1]

    def sjis(self, ids):
        return b''.join(self.codes[t] for t in ids)

    def decode_sjis(self, data):
        out = []
        for k in range(0, len(data) - 1, 2):
            c = data[k:k + 2]
            if c[0] == 0:
                break
            out.append(self.tokens[self.by_code[c]])
        return ''.join(out)

    # ------------------------------------------------------------------ io
    def save(self, path):
        json.dump({'multi': self.tokens[FIRST_MULTI:]}, open(path, 'w', encoding='utf8'),
                  ensure_ascii=False, indent=0)

    @classmethod
    def load(cls, path):
        return cls(json.load(open(path, encoding='utf8'))['multi'])

    @classmethod
    def build(cls, lines, budget=NGLYPH - FIRST_MULTI):
        """BPE merges over the words of the corpus (weighted by frequency)."""
        words = collections.Counter()
        for ln in lines:
            for w in normalize(ln).split(' '):
                if w:
                    words[w] += 1
        seqs = {w: list(w) for w in words}
        multi = []
        known = set()
        pair_count = collections.Counter()
        where = collections.defaultdict(set)
        for w, sq in seqs.items():
            c = words[w]
            for a, b in zip(sq, sq[1:]):
                pair_count[(a, b)] += c
                where[(a, b)].add(w)
        while len(multi) < budget and pair_count:
            (a, b), cnt = max(pair_count.items(), key=lambda kv: kv[1])
            if cnt < 2:
                break
            new = a + b
            del pair_count[(a, b)]
            if new not in known:
                known.add(new)
                multi.append(new)
            for w in list(where.pop((a, b), ())):
                sq = seqs[w]
                c = words[w]
                for x, y in zip(sq, sq[1:]):
                    pair_count[(x, y)] -= c
                    if pair_count[(x, y)] <= 0:
                        pair_count.pop((x, y), None)
                i, out = 0, []
                while i < len(sq):
                    if i + 1 < len(sq) and sq[i] == a and sq[i + 1] == b:
                        out.append(new)
                        i += 2
                    else:
                        out.append(sq[i])
                        i += 1
                seqs[w] = out
                for x, y in zip(out, out[1:]):
                    pair_count[(x, y)] += c
                    where[(x, y)].add(w)
        return cls(multi)


def normalize(text):
    for a, b in NORMAL.items():
        text = text.replace(a, b)
    return text


# ---------------------------------------------------------------------- nibble codes
def code_space(P):
    P0, P1, P2 = P
    return [16 - P0, P0 * (16 - P1), P0 * P1 * (16 - P2), P0 * P1 * P2 * 16]


def code_len(c, P):
    n = 0
    for k, size in enumerate(code_space(P)):
        if c < n + size:
            return k + 1
        n += size
    raise ValueError('code out of range')


def encode_code(c, P):
    """Nibbles for code index c (inverse of the EXE decoder at 0x800457EC)."""
    P0, P1, P2 = P
    sizes = code_space(P)
    if c < sizes[0]:
        return [c + P0]
    c -= sizes[0]
    if c < sizes[1]:
        n0, r = divmod(c, 16 - P1)
        return [n0, r + P1]
    c -= sizes[1]
    if c < sizes[2]:
        q, r = divmod(c, 16 - P2)
        n0, n1 = divmod(q, P1)
        return [n0, n1, r + P2]
    c -= sizes[2]
    q, n3 = divmod(c, 16)
    q, n2 = divmod(q, P2)
    n0, n1 = divmod(q, P1)
    return [n0, n1, n2, n3]


def best_params(freqs, nterm):
    """P minimising the nibble count; freqs = token frequencies sorted descending."""
    best = None
    for P0 in range(1, 16):
        for P1 in range(1, 16):
            for P2 in range(1, 16):
                P = (P0, P1, P2)
                if sum(code_space(P)) < len(freqs) + 1:
                    continue
                term = 16 - P0
                tot = nterm * code_len(term, P)
                for i, f in enumerate(freqs):
                    tot += f * code_len(i if i < term else i + 1, P)
                if best is None or tot < best[0]:
                    best = (tot, P)
    return best[1]


class Table:
    """A chapter table: table index -> token id, ordered by frequency, with P params."""
    def __init__(self, d, strings_ids, P=None):
        cnt = collections.Counter()
        for ids in strings_ids:
            cnt.update(ids)
        order = sorted((t for t in range(len(d.tokens)) if d.tokens[t] is not None),
                       key=lambda t: (-cnt[t], t))
        self.d = d
        self.order = order
        self.pos = {t: i for i, t in enumerate(order)}
        self.P = P or best_params([cnt[t] for t in order], len(strings_ids))
        self.term = 16 - self.P[0]

    def code_index(self, tid):
        i = self.pos[tid]
        return i if i < self.term else i + 1

    def nibbles(self, ids):
        out = []
        for t in ids:
            out += encode_code(self.code_index(t), self.P)
        out += encode_code(self.term, self.P)
        return out

    def header_and_entries(self):
        out = bytearray(bytes([self.P[0], self.P[1], self.P[2], 0x10]))
        for t in self.order:
            out += t.to_bytes(2, 'little') + self.d.codes[t]
        return bytes(out)
