"""Tiny two-pass MIPS R3000 assembler for game hooks (no delay-slot magic).

    code, labels = assemble(source, base=0x8000B800, symbols={'GsBG': 0x80160EF0})

Syntax: one instruction per line, ';' or '#' comments, 'label:' definitions.
Registers: $zero..$ra / $0..$31 (with or without '$').
Operands may be expressions using labels/symbols, + - * << >> & |, and
%hi(x) / %lo(x) (for lui/addiu pairs, %hi is adjusted for sign).
Pseudo: nop, move, li, la, b, beqz, bnez, bal-free 'call x' (= jal x / nop),
        neg, not, subiu.
Directives: .word, .half, .byte, .align n, .space n, .ascii "s".
Branch delay slots are NOT filled automatically: write the slot instruction.
"""
import re
import struct

REGS = {n: i for i, n in enumerate(
    'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split())}
REGS['s8'] = 30

R3 = {'addu': 0x21, 'subu': 0x23, 'and': 0x24, 'or': 0x25, 'xor': 0x26, 'nor': 0x27,
      'slt': 0x2A, 'sltu': 0x2B, 'add': 0x20, 'sub': 0x22}
RSH = {'sll': 0x00, 'srl': 0x02, 'sra': 0x03}
RSHV = {'sllv': 0x04, 'srlv': 0x06, 'srav': 0x07}
RMD = {'mult': 0x18, 'multu': 0x19, 'div': 0x1A, 'divu': 0x1B}
RMF = {'mfhi': 0x10, 'mflo': 0x12, 'mthi': 0x11, 'mtlo': 0x13}
IMM = {'addiu': 0x09, 'addi': 0x08, 'slti': 0x0A, 'sltiu': 0x0B, 'andi': 0x0C, 'ori': 0x0D, 'xori': 0x0E}
MEM = {'lb': 0x20, 'lh': 0x21, 'lwl': 0x22, 'lw': 0x23, 'lbu': 0x24, 'lhu': 0x25, 'lwr': 0x26,
       'sb': 0x28, 'sh': 0x29, 'swl': 0x2A, 'sw': 0x2B, 'swr': 0x2E}
BR2 = {'beq': 0x04, 'bne': 0x05}
BR1 = {'blez': (0x06, 0), 'bgtz': (0x07, 0), 'bltz': (0x01, 0), 'bgez': (0x01, 1)}


class AsmError(Exception):
    pass


LOADS = ('lb', 'lbu', 'lh', 'lhu', 'lw', 'lwl', 'lwr')


def regs_read(mn, ops):
    """Registers an instruction reads (for the load-delay hazard check)."""
    def r(o):
        o = o.strip()
        m = re.match(r'^.*\((\$?\w+)\)$', o)
        if m:
            return [reg(m.group(1))]
        try:
            return [reg(o)]
        except AsmError:
            return []
    if mn in ('nop', 'li', 'la', 'lui', 'j', 'jal', 'call', 'b', 'mfhi', 'mflo', '.word', '.half', '.byte'):
        return []
    if mn in LOADS:
        return r(ops[1])
    if mn in MEM:                       # stores: value and base
        return r(ops[0]) + r(ops[1])
    if mn in ('jr', 'jalr', 'mthi', 'mtlo') or mn in BR1 or mn in ('beqz', 'bnez'):
        return r(ops[0])
    if mn in BR2 or mn in RMD:
        return r(ops[0]) + r(ops[1])
    out = []
    for o in ops[1:]:
        out += r(o)
    return out


def reg(s):
    s = s.strip().lstrip('$')
    if s.isdigit():
        return int(s)
    if s not in REGS:
        raise AsmError('bad register %r' % s)
    return REGS[s]


def split_ops(s):
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


class Assembler:
    def __init__(self, base, symbols=None):
        self.nops_added = 0
        self.base = base
        self.symbols = dict(symbols or {})

    def ev(self, expr, final):
        e = expr.strip()

        def hi(m):
            v = self.ev(m.group(1), final)
            return str(((v + 0x8000) >> 16) & 0xFFFF)

        def lo(m):
            v = self.ev(m.group(1), final)
            lo16 = v & 0xFFFF
            return str(lo16 - 0x10000 if lo16 & 0x8000 else lo16)
        e = re.sub(r'%hi\(([^()]*)\)', hi, e)
        e = re.sub(r'%lo\(([^()]*)\)', lo, e)

        def sym(m):
            n = m.group(0)
            if n in self.symbols:
                return str(self.symbols[n])
            if final:
                raise AsmError('undefined symbol %r' % n)
            return '0'
        e = re.sub(r'(?<![0-9xXa-fA-F])[A-Za-z_.][A-Za-z0-9_.]*', sym, e)
        try:
            return int(eval(e, {'__builtins__': {}}, {}))
        except Exception:
            raise AsmError('bad expression %r' % expr)

    def mem(self, op, final):
        m = re.match(r'^(.*)\((\$?\w+)\)$', op.strip())
        if not m:
            raise AsmError('bad memory operand %r' % op)
        off = self.ev(m.group(1) or '0', final)
        return off, reg(m.group(2))

    def encode(self, mn, ops, pc, final):
        def imm16(v):
            if final and not -0x8000 <= v <= 0xFFFF:
                raise AsmError('immediate out of range: %d' % v)
            return v & 0xFFFF

        def branch(target):
            off = (target - (pc + 4)) >> 2
            if final and not -0x8000 <= off <= 0x7FFF:
                raise AsmError('branch out of range')
            return off & 0xFFFF
        if mn == 'nop':
            return [0]
        if mn == 'move':
            return [(reg(ops[1]) << 21) | (reg(ops[0]) << 11) | 0x21]
        if mn == 'neg':
            return [(reg(ops[1]) << 16) | (reg(ops[0]) << 11) | 0x23]
        if mn == 'not':
            return [(reg(ops[1]) << 21) | (reg(ops[0]) << 11) | 0x27]
        if mn in ('li', 'la'):
            rt = reg(ops[0])
            v = self.ev(ops[1], final) & 0xFFFFFFFF
            if mn == 'li' and v <= 0xFFFF:
                return [(0x0D << 26) | (rt << 16) | v, 0]  # ori (fixed 2 words for pass stability)
            if mn == 'li' and v >= 0xFFFF8000:
                return [(0x09 << 26) | (rt << 16) | (v & 0xFFFF), 0]
            hi = ((v + 0x8000) >> 16) & 0xFFFF
            lo = v & 0xFFFF
            return [(0x0F << 26) | (rt << 16) | hi, (0x09 << 26) | (rt << 21) | (rt << 16) | lo]
        if mn in R3:
            return [(reg(ops[1]) << 21) | (reg(ops[2]) << 16) | (reg(ops[0]) << 11) | R3[mn]]
        if mn in RSH:
            return [(reg(ops[1]) << 16) | (reg(ops[0]) << 11) | ((self.ev(ops[2], final) & 31) << 6) | RSH[mn]]
        if mn in RSHV:
            return [(reg(ops[2]) << 21) | (reg(ops[1]) << 16) | (reg(ops[0]) << 11) | RSHV[mn]]
        if mn in RMD:
            return [(reg(ops[0]) << 21) | (reg(ops[1]) << 16) | RMD[mn]]
        if mn in RMF:
            r = reg(ops[0])
            return [(r << 11) | RMF[mn]] if mn.startswith('mf') else [(r << 21) | RMF[mn]]
        if mn == 'jr':
            return [(reg(ops[0]) << 21) | 0x08]
        if mn == 'jalr':
            rd = reg(ops[1]) if len(ops) > 1 else 31
            rs = reg(ops[0])
            return [(rs << 21) | (rd << 11) | 0x09]
        if mn == 'subiu':
            return [(0x09 << 26) | (reg(ops[1]) << 21) | (reg(ops[0]) << 16) | imm16(-self.ev(ops[2], final))]
        if mn in IMM:
            return [(IMM[mn] << 26) | (reg(ops[1]) << 21) | (reg(ops[0]) << 16) | imm16(self.ev(ops[2], final))]
        if mn == 'lui':
            return [(0x0F << 26) | (reg(ops[0]) << 16) | imm16(self.ev(ops[1], final))]
        if mn in MEM:
            off, base = self.mem(ops[1], final)
            return [(MEM[mn] << 26) | (base << 21) | (reg(ops[0]) << 16) | imm16(off)]
        if mn in BR2:
            return [(BR2[mn] << 26) | (reg(ops[0]) << 21) | (reg(ops[1]) << 16) | branch(self.ev(ops[2], final))]
        if mn in ('beqz', 'bnez'):
            code = 0x04 if mn == 'beqz' else 0x05
            return [(code << 26) | (reg(ops[0]) << 21) | branch(self.ev(ops[1], final))]
        if mn == 'b':
            return [(0x04 << 26) | branch(self.ev(ops[0], final))]
        if mn in BR1:
            code, rt = BR1[mn]
            return [(code << 26) | (reg(ops[0]) << 21) | (rt << 16) | branch(self.ev(ops[1], final))]
        if mn in ('j', 'jal'):
            t = self.ev(ops[0], final)
            if final and (t & 0xF0000000) != ((pc + 4) & 0xF0000000):
                raise AsmError('jump out of region')
            return [((0x02 if mn == 'j' else 0x03) << 26) | ((t >> 2) & 0x3FFFFFF)]
        if mn == 'call':
            t = self.ev(ops[0], final)
            return [(0x03 << 26) | ((t >> 2) & 0x3FFFFFF), 0]
        raise AsmError('unknown mnemonic %r' % mn)

    def run(self, src):
        for final in (False, True):
            pc = self.base
            out = bytearray()
            scope = '_'
            pending = None              # register loaded by the previous instruction
            for lineno, line in enumerate(src.splitlines(), 1):
                line = re.split(r'[;#]', line, 1)[0].strip()
                # '@name' labels are local to the preceding global label
                g = re.match(r'^([A-Za-z_.][\w.]*):', line)
                if g:
                    scope = g.group(1)
                line = re.sub(r'@(\w+)', lambda m: '%s__%s' % (scope, m.group(1)), line)
                try:
                    while True:
                        m = re.match(r'^([A-Za-z_.][\w.]*):\s*(.*)$', line)
                        if not m:
                            break
                        if not final:
                            if m.group(1) in self.symbols and self.symbols[m.group(1)] != pc:
                                raise AsmError('duplicate label %s' % m.group(1))
                        self.symbols[m.group(1)] = pc
                        line = m.group(2).strip()
                    if not line:
                        continue
                    parts = line.split(None, 1)
                    mn = parts[0].lower()
                    ops = split_ops(parts[1]) if len(parts) > 1 else []
                    if mn.startswith('.'):
                        pending = None
                    if mn == '.word':
                        b = b''.join(struct.pack('<I', self.ev(o, final) & 0xFFFFFFFF) for o in ops)
                    elif mn == '.half':
                        b = b''.join(struct.pack('<H', self.ev(o, final) & 0xFFFF) for o in ops)
                    elif mn == '.byte':
                        b = bytes(self.ev(o, final) & 0xFF for o in ops)
                    elif mn == '.space':
                        b = bytes(self.ev(ops[0], final))
                    elif mn == '.align':
                        a = self.ev(ops[0], final)
                        b = bytes((-(pc - self.base)) % a)
                    elif mn == '.ascii':
                        b = eval(parts[1]).encode('ascii')
                    elif mn == '.incbin':
                        b = self.symbols['__bin_' + ops[0]]
                    else:
                        if pc & 3:
                            raise AsmError('unaligned instruction')
                        pad = b''
                        if pending is not None and pending != 0 and pending in regs_read(mn, ops):
                            pad = bytes(4)                  # fill the load delay slot with a nop
                            if final:
                                self.nops_added += 1
                        b = pad + b''.join(struct.pack('<I', w)
                                           for w in self.encode(mn, ops, pc + len(pad), final))
                        pending = reg(ops[0]) if mn in LOADS else None
                except AsmError as e:
                    raise AsmError('line %d: %s\n    %s' % (lineno, e, line))
                out += b
                pc += len(b)
        return bytes(out), self.symbols


def assemble(src, base, symbols=None, blobs=None):
    a = Assembler(base, symbols)
    for k, v in (blobs or {}).items():
        a.symbols['__bin_' + k] = v
    code, syms = a.run(src)
    syms['__nops_added'] = a.nops_added
    return code, syms
