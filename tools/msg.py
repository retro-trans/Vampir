"""Show the villager messages that use a row, fragment by fragment (current English).

    python tools/msg.py M1#1234 [M1#...]      every message containing the row
    python tools/msg.py M1@283525             one message by its SQC position

Each fragment prints as [#k] text (v = a per-message variant is in effect), names as {NAME},
pauses as <p>, then the assembled boxes as check.py measures them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402
import fit  # noqa: E402
import talk  # noqa: E402


def show(ch, m, en, var):
    out = []
    for i, p in enumerate(m['parts']):
        if isinstance(p, int):
            t, key = check.frag(m, i, en, var)
            out.append('[#%d%s]%r' % (p, ('v@%s' % key[1]) if key else '', t))
        else:
            out.append({'NL': ' / ', 'WAIT': ' |W| ', 'CLEAR': '', 'PAUSE': '<p>', 'NAME': '{NAME}',
                        'PARTNER': '{PARTNER}', 'PLAYER': '\n  PLAYER: ', 'VILLAGER': '\n  VILLAGER: '}[p])
    print('%s msg %d (villager %d):%s' % (ch, m['pos'], m['villager'], ''.join(out)))
    bx, _ = check.boxes(m, en, var)
    for b in bx:
        print('    | %s   (%d lines)' % (' / '.join(b), sum(fit.wrap(x, 240) for x in b)))
    print()


def main():
    for arg in sys.argv[1:]:
        ch = arg[:2]
        en, var = check.translations(ch)
        ms = talk.messages(ch, len(en))
        if '@' in arg:
            pos = int(arg.split('@')[1])
            for m in ms:
                if m['pos'] <= pos < m['end']:
                    show(ch, m, en, var)
        else:
            k = int(arg.split('#')[1])
            print('%s#%d jp: %s' % (ch, k, check.JP.get(k)))
            for m in ms:
                if k in m['parts']:
                    show(ch, m, en, var)


if __name__ == '__main__':
    main()
