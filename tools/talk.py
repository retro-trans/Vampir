"""Villager conversation structure from M?/C/M?.SQC (one 4 KB script per villager).

Variants: {"msg": message position} changes every occurrence of the string in that message,
{"ref": position of the 0D reference} changes that occurrence only.

Message runs are recognised by their tokens (heuristic, the rest of the bytecode is
skipped):  11 player speaks | 12 villager speaks | 0D hh ll STC string | 0F newline |
10 wait for button | 0C clear | 18 player name | 19 partner name | 1A nn pause nn frames
(used between dots: "..." <pause> "..." <pause>).

    msgs = messages('M0')        # [{'villager', 'pos', 'parts': [...]}]
    python tools/talk.py M0 [villager]     prints the conversations
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKENS = {0x0F: 'NL', 0x10: 'WAIT', 0x0C: 'CLEAR', 0x18: 'NAME', 0x19: 'PARTNER', 0x11: 'PLAYER', 0x12: 'VILLAGER'}


def sqc(ch):
    return open(os.path.join(ROOT, 'work', 'source', 'disc', ch, 'C', ch + '.SQC'), 'rb').read()


def runs(blk, nstr):
    """Yield (pos, parts) for every run that contains at least one string."""
    i = 0
    n = len(blk)
    while i < n:
        parts, offs = [], []
        start = i
        j = i
        while j < n:
            b = blk[j]
            if b == 0x0D and j + 2 < n and (blk[j + 1] << 8 | blk[j + 2]) < nstr:
                parts.append(blk[j + 1] << 8 | blk[j + 2])
                offs.append(j)
                j += 3
            elif b == 0x1A and parts and j + 1 < n and blk[j + 1] <= 60:
                parts.append('PAUSE')
                offs.append(j)
                j += 2
            elif b in TOKENS and (parts or b in (0x11, 0x12)):
                parts.append(TOKENS[b])
                offs.append(j)
                j += 1
            else:
                break
        ok = bool(parts) and (parts[0] in ('PLAYER', 'VILLAGER') or bool(start and blk[start - 1] in (0x11, 0x12))
              or parts[-1] in ('WAIT', 'CLEAR'))
        if any(isinstance(p, int) for p in parts) and ok:
            yield start, parts, j, offs
            i = j
        else:
            i = max(j, i + 1)


def messages(ch, nstr=None):
    if nstr is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from stc import Stc
        nstr = Stc(os.path.join(ROOT, 'work', 'source', 'disc', ch, 'C', ch + '.STC')).count()
    d = sqc(ch)
    out = []
    for v in range(len(d) // 4096):
        blk = d[v * 4096:(v + 1) * 4096]
        for pos, parts, end, offs in runs(blk, nstr):
            out.append({'villager': v, 'pos': v * 4096 + pos, 'parts': parts, 'end': v * 4096 + end,
                        'offs': [v * 4096 + o for o in offs]})
    return out


def render(parts, text):
    out = []
    for p in parts:
        if isinstance(p, int):
            out.append(text[p])
        elif p == 'NL':
            out.append(' / ')
        elif p in ('NAME', 'PARTNER'):
            out.append('{%s}' % p)
        elif p in ('PLAYER', 'VILLAGER'):
            out.append('\n  [%s] ' % p)
        elif p == 'WAIT':
            out.append(' ▼')
    return ''.join(out)


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from stc import Stc
    ch = sys.argv[1]
    s = Stc(os.path.join(ROOT, 'work', 'source', 'disc', ch, 'C', ch + '.STC'))
    t = s.strings()
    ms = messages(ch, len(t))
    used = set(p for m in ms for p in m['parts'] if isinstance(p, int))
    print('messages', len(ms), 'strings used', len(used), 'of', len(t))
    if len(sys.argv) > 2:
        for m in ms:
            if m['villager'] == int(sys.argv[2]):
                print(hex(m['pos']), render(m['parts'], t))


def patch_run(data, pos, old, new, nstr, single=False):
    """Repoint 0D <old> to <new>: single=True -> only the reference at pos (a "ref" variant),
    else every reference of <old> in the message run starting at pos (a "msg" variant)."""
    d = bytearray(data)
    if single:
        if not (d[pos] == 0x0D and (d[pos + 1] << 8 | d[pos + 2]) == old):
            raise ValueError('string %d is not referenced at 0x%X' % (old, pos))
        d[pos + 1], d[pos + 2] = new >> 8, new & 0xFF
        return bytes(d)
    j, n, hits = pos, len(d), 0
    end = (pos // 4096 + 1) * 4096
    while j < min(n, end):
        b = d[j]
        if b == 0x0D and j + 2 < n:              # (an earlier variant may already point >= nstr)
            if (d[j + 1] << 8 | d[j + 2]) == old:
                d[j + 1], d[j + 2] = new >> 8, new & 0xFF
                hits += 1
            j += 3
        elif b in TOKENS:
            j += 1
        elif b == 0x1A and j + 1 < n and d[j + 1] <= 60:
            j += 2
        else:
            break
    if not hits:
        raise ValueError('string %d not found in the message at 0x%X' % (old, pos))
    return bytes(d)
