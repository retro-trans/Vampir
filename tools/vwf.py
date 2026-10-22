"""VWF / 4x font hooks for SLPS_019.32 (see docs/VWF.md).

Every text renderer of the game builds one 12x12 SPRT per glyph from the 12 px font.
The hooks replace that with EMIT: a "glyph" is now a token (one or more letters,
see tools/vtext.py) and each letter becomes a POLY_FT4 that samples the 4x atlas
(tools/font_atlas.py).  The token width table at 0x8008444C keeps driving layout,
centring and pen advance, so the game's own logic stays in charge.

    code, symbols, patches = build(tokens)     # patches: [(addr, bytes)]
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from masm import assemble  # noqa: E402

BASE = 0x800C6E00          # EXE extension (past the BSS end 0x800C6CD8 + InitHeap header)
LIMIT = 0x800CB800         # overlays start here
# POLY_FT4 pools (base, per-frame stride, quads per frame): memory the hooks free or that
# nothing uses: the game's own SPRT and DR_TPAGE text buffers, and free kernel RAM.
POOLS = [(0x800AC790, 4800, 120), (0x800AED10, 0x300, 19), (0x8000B800, 4600, 115)]
QMAX = sum(p[2] for p in POOLS)
WIDTHS = 0x8008444C        # u8 per glyph (token), 1323 entries
NGLYPH = 1323
DECODE = 0x800457EC
SPACE_TOK = 0x20

SYMS = {
    'QMAX': QMAX, 'WIDTHS': WIDTHS, 'DECODE': DECODE,
    'SPACE_TOK': SPACE_TOK,
    'BOX_RET': 0x80044D9C, 'CEN_LOOP': 0x80045138, 'CEN_END': 0x800453CC, 'CEN_RET': 0x80045404,
    'LINE_LOOP': 0x800454BC, 'LINE_END_RET': 0x800457BC, 'LAY_RET': 0x80044580,
    'STRCAT': 0x8006109C,
}

ASM = r'''
; ---------------------------------------------------------------- EMIT
; a0 token, a1 x, a2 y, a3 attr, t0 visible height (1..12), t1 rows skipped at the top
; returns v0 = first quad (0 if none), v1 = last quad; preserves everything else but ra
EMIT:
    addiu $sp, $sp, -56
    sw $t0, 0($sp)
    sw $t1, 4($sp)
    sw $t2, 8($sp)
    sw $t3, 12($sp)
    sw $t4, 16($sp)
    sw $t5, 20($sp)
    sw $t6, 24($sp)
    sw $t7, 28($sp)
    sw $t8, 32($sp)
    sw $t9, 36($sp)
    sw $a0, 40($sp)
    sw $a1, 44($sp)
    sw $a2, 48($sp)
    sw $a3, 52($sp)
    move $v0, $zero
    move $v1, $zero
    sltiu $t2, $a0, NTOK         ; unknown glyph (untranslated Japanese): draw nothing
    beqz $t2, @done
    nop
    la $t2, TOKOFF
    sll $t3, $a0, 1
    addu $t2, $t2, $t3
    lhu $t3, 0($t2)
    la $t2, TOKDATA
    addu $t2, $t2, $t3
    lbu $t3, 0($t2)              ; letter count
    addiu $t2, $t2, 1
    andi $a3, $a3, 7
    sll $a3, $a3, 1
    la $t4, CLUTS
    addu $t4, $t4, $a3
    lhu $a3, 0($t4)              ; a3 = CLUT id
    sll $t1, $t1, 2              ; texel rows skipped
    sll $t0, $t0, 2              ; texel rows shown
@loop:
    beqz $t3, @done
    nop
    lbu $t4, 0($t2)
    addiu $t2, $t2, 1
    addiu $t3, $t3, -1
    la $t5, LETTERS
    sll $t4, $t4, 3
    addu $t5, $t5, $t4           ; {u, v, w, tpage, xoff, adv}
    lbu $t6, 2($t5)              ; w (px)
    beqz $t6, @adv
    nop
    lui $t8, 0x800b
    lhu $t9, -0x9d6($t8)         ; quad counter (the game resets it every frame)
    nop
    sltiu $t4, $t9, QMAX
    beqz $t4, @adv               ; all pools full: drop the letter
    addiu $t4, $t9, 1
    sh $t4, -0x9d6($t8)
    la $t8, POOLS                ; {base, frame stride, capacity} x n
@pool:
    lw $t4, 8($t8)
    nop
    sltu $at, $t9, $t4
    bnez $at, @inpool
    nop
    subu $t9, $t9, $t4
    b @pool
    addiu $t8, $t8, 12
@inpool:
    sll $t4, $t9, 5
    sll $t9, $t9, 3
    addu $t9, $t9, $t4           ; index * 40
    lw $t4, 0($t8)
    nop
    addu $t9, $t9, $t4
    lui $at, 0x800c
    lh $at, 0x54cc($at)          ; frame buffer index 0/1
    lw $t4, 4($t8)
    beqz $at, @f0
    move $t8, $t9
    addu $t8, $t8, $t4
@f0:                             ; t8 = quad
    lui $t4, 0x0900
    sw $t4, 0($t8)               ; len 9, end of list
    li $t4, 0x2C808080
    sw $t4, 4($t8)
    lb $t4, 4($t5)               ; xoff
    nop
    addu $t4, $a1, $t4           ; x0
    addu $t7, $t4, $t6           ; x1
    andi $t4, $t4, 0xffff
    andi $t7, $t7, 0xffff
    sll $t9, $a2, 16             ; y0 << 16
    or $at, $t9, $t4
    sw $at, 8($t8)
    or $at, $t9, $t7
    sw $at, 16($t8)
    srl $t9, $t0, 2
    addu $t9, $t9, $a2
    sll $t9, $t9, 16             ; y1 << 16
    or $at, $t9, $t4
    sw $at, 24($t8)
    or $at, $t9, $t7
    sw $at, 32($t8)
    lbu $t4, 0($t5)              ; u0
    sll $t7, $t6, 2
    addu $t7, $t7, $t4           ; u1
    lbu $t9, 1($t5)
    nop
    addu $t9, $t9, $t1           ; v0
    sll $t9, $t9, 8
    sll $at, $a3, 16
    or $at, $at, $t9
    or $at, $at, $t4
    sw $at, 12($t8)              ; uv0 + clut
    lbu $at, 3($t5)
    nop
    sll $at, $at, 16
    or $at, $at, $t9
    or $at, $at, $t7
    sw $at, 20($t8)              ; uv1 + tpage
    lbu $t9, 1($t5)
    nop
    addu $t9, $t9, $t1
    addu $t9, $t9, $t0           ; v1
    sll $t9, $t9, 8
    or $at, $t9, $t4
    sw $at, 28($t8)
    or $at, $t9, $t7
    sw $at, 36($t8)
    bnez $v0, @chain
    nop
    move $v0, $t8
    b @next
    nop
@chain:
    lui $t4, 0x0900
    lui $at, 0x00ff
    ori $at, $at, 0xffff
    and $at, $t8, $at
    or $t4, $t4, $at
    sw $t4, 0($v1)
@next:
    move $v1, $t8
@adv:
    lbu $t4, 5($t5)
    nop
    b @loop
    addu $a1, $a1, $t4
@done:
    lw $t0, 0($sp)
    lw $t1, 4($sp)
    lw $t2, 8($sp)
    lw $t3, 12($sp)
    lw $t4, 16($sp)
    lw $t5, 20($sp)
    lw $t6, 24($sp)
    lw $t7, 28($sp)
    lw $t8, 32($sp)
    lw $t9, 36($sp)
    lw $a0, 40($sp)
    lw $a1, 44($sp)
    lw $a2, 48($sp)
    lw $a3, 52($sp)
    jr $ra
    addiu $sp, $sp, 56

; ---------------------------------------------------------------- box grid (0x80044758)
; from 0x80044A24 (replaces 'move s7,a2'); v0 = cell, a2 = glyph; t5 h, t6 y, t7 x,
; t8 first prim, s6 last prim, s5 line, t9 = 0x800B0000
BOX:
    move $s7, $a2
    andi $a0, $a2, 0xffff
    sltiu $at, $a0, 0x801
    beqz $at, @skip
    srl $a3, $v0, 12
    move $t1, $zero
    lbu $at, -0x9d9($t9)         ; scroll animation running
    nop
    beqz $at, @noscr
    nop
    bnez $s5, @noscr
    nop
    li $t1, 12
    subu $t1, $t1, $t5           ; line 0 scrolls out at the top
@noscr:
    move $a1, $t7
    move $a2, $t6
    jal EMIT
    move $t0, $t5
    beqz $v0, @adv
    nop
    bnez $t8, @link
    nop
    b @last
    move $t8, $v0
@link:
    lw $at, 0($s6)
    lui $a0, 0xff00
    and $at, $at, $a0
    lui $a0, 0x00ff
    ori $a0, $a0, 0xffff
    and $a0, $v0, $a0
    or $at, $at, $a0
    sw $at, 0($s6)
@last:
    move $s6, $v1
@adv:
    la $a0, WIDTHS
    addu $a0, $a0, $s7
    lbu $a0, 0($a0)
    nop
    addu $t7, $t7, $a0
@skip:
    j BOX_RET
    nop

; ---------------------------------------------------------------- centred line (0x80044FE8)
; from 0x80045158; t0/a0 = glyph, s2 = x, s0 = index, t5 first, t2 last, attr at 0x40(sp)
CEN:
    andi $t3, $t0, 0xffff
    lui $at, 0x800b
    lh $a2, -0x9de($at)
    lbu $a3, 0x40($sp)
    move $a0, $t3
    move $a1, $s2
    move $t1, $zero
    jal EMIT
    addiu $t0, $zero, 12
    beqz $v0, @adv
    nop
    bnez $t5, @link
    nop
    b @last
    move $t5, $v0
@link:
    lw $at, 0($t2)
    lui $a0, 0xff00
    and $at, $at, $a0
    lui $a0, 0x00ff
    ori $a0, $a0, 0xffff
    and $a0, $v0, $a0
    or $at, $at, $a0
    sw $at, 0($t2)
@last:
    move $t2, $v1
@adv:
    la $a0, WIDTHS
    addu $a0, $a0, $t3
    lbu $a0, 0($a0)
    nop
    addu $s2, $s2, $a0
    addiu $a2, $s0, 1
    move $s0, $a2
    sll $a2, $a2, 16
    sra $a2, $a2, 16
    slti $a2, $a2, 0x18
    beqz $a2, @end
    nop
    j CEN_LOOP
    nop
@end:
    j CEN_END
    nop

CEN_END_HOOK:                    ; 0x800453CC: nothing drawn -> do not link
    beqz $t5, @none
    nop
    lui $a0, 0xff
    j 0x800453D4
    ori $a0, $a0, 0xffff
@none:
    j CEN_RET
    nop

; ---------------------------------------------------------------- line (0x80045434)
; from 0x80045500; t0 = glyph, s1 first, s0 last, attr at 0x10(sp)
LINE:
    andi $t3, $t0, 0xffff
    lui $at, 0x800b
    lh $a1, -0x9e0($at)
    lh $a2, -0x9de($at)
    lbu $a3, 0x10($sp)
    move $a0, $t3
    move $t1, $zero
    jal EMIT
    addiu $t0, $zero, 12
    beqz $v0, @adv
    nop
    bnez $s1, @link
    nop
    b @last
    move $s1, $v0
@link:
    lw $at, 0($s0)
    lui $a0, 0xff00
    and $at, $at, $a0
    lui $a0, 0x00ff
    ori $a0, $a0, 0xffff
    and $a0, $v0, $a0
    or $at, $at, $a0
    sw $at, 0($s0)
@last:
    move $s0, $v1
@adv:
    la $a0, WIDTHS
    addu $a0, $a0, $t3
    lbu $a0, 0($a0)
    lui $at, 0x800b
    lhu $v0, -0x9e0($at)
    nop
    addu $v0, $v0, $a0
    sh $v0, -0x9e0($at)
    j LINE_LOOP
    nop

LINE_END_HOOK:                   ; 0x80045780
    beqz $s1, @none
    nop
    lui $a0, 0xff
    j 0x80045788
    ori $a0, $a0, 0xffff
@none:
    j LINE_END_RET
    nop

; ---------------------------------------------------------------- layout (0x80044478)
; from 0x800444F8 with t2 = table index; returns to LAY_RET with t2 = glyph after updating
; col (0x800AF32E), line (0x800AF32F) and pen x (0x800AF330).  Adds word wrap: at a space,
; if the next word does not fit, the line breaks there (the space becomes an empty cell).
LAYOUT:
    addiu $sp, $sp, -40
    sw $s0, 0($sp)
    sw $s1, 4($sp)
    sw $s2, 8($sp)
    sw $s3, 12($sp)
    sw $s4, 16($sp)
    sw $s5, 20($sp)
    sw $s6, 24($sp)
    sw $s7, 28($sp)
    lui $s3, 0x800b
    lw $v0, -0xce8($s3)          ; table
    andi $t2, $t2, 0xffff
    sll $v1, $t2, 2
    addu $v0, $v0, $v1
    lhu $s0, 0($v0)              ; glyph
    la $s1, WIDTHS
    addu $v0, $s1, $s0
    lbu $s2, 0($v0)              ; width
    li $v0, SPACE_TOK
    bne $s0, $v0, @nonspace
    nop
    lhu $a0, -0xcd0($s3)
    nop
    beqz $a0, @place             ; space at the line start: keep it
    nop
    lw $s4, -0xcf0($s3)          ; decoder state
    lbu $s5, -0xcec($s3)
    move $s6, $zero
    sw $zero, 32($sp)            ; tokens in the next word
    lhu $s7, -0xcda($s3)         ; TERM
@look:
    jal DECODE
    nop
    andi $v0, $v0, 0xffff
    beq $v0, $s7, @lookend
    sltu $v1, $v0, $s7
    bnez $v1, @noadj
    nop
    addiu $v0, $v0, -1
@noadj:
    lw $v1, -0xce8($s3)
    sll $v0, $v0, 2
    addu $v1, $v1, $v0
    lhu $v0, 0($v1)
    li $v1, SPACE_TOK
    beq $v0, $v1, @lookend
    addu $v1, $s1, $v0
    lbu $v1, 0($v1)
    nop
    addu $s6, $s6, $v1
    lw $v1, 32($sp)
    nop
    addiu $v1, $v1, 1
    sw $v1, 32($sp)
    sltiu $v0, $s6, 0x200
    bnez $v0, @look
    nop
@lookend:
    sw $s4, -0xcf0($s3)
    sb $s5, -0xcec($s3)
    lbu $v0, -0xcd2($s3)         ; the word must also fit the cells left in the line
    lw $v1, 32($sp)
    lbu $a1, -0x9e8($s3)
    addu $v0, $v0, $v1
    addiu $v0, $v0, 1
    sltu $v0, $a1, $v0
    bnez $v0, @brk
    nop
    lhu $a0, -0xcd0($s3)
    lhu $a1, -0x9e2($s3)
    addu $v0, $a0, $s2
    addu $v0, $v0, $s6
    sltu $v0, $a1, $v0
    beqz $v0, @place
    nop
@brk:
    lbu $v0, -0xcd1($s3)         ; break here: newline, the space is not drawn
    sb $zero, -0xcd2($s3)
    addiu $v0, $v0, 1
    sb $v0, -0xcd1($s3)
    sh $zero, -0xcd0($s3)
    b @ret
    li $s0, 0xFFF
@nonspace:
    lhu $a0, -0xcd0($s3)
    lhu $a1, -0x9e2($s3)
    addu $v0, $a0, $s2
    sltu $v0, $a1, $v0
    bnez $v0, @wrap              ; a word longer than the line: break inside it
    nop
@place:
    lbu $v0, -0xcd2($s3)
    lbu $v1, -0x9e8($s3)         ; cells per line
    addiu $v0, $v0, 1
    sltu $v1, $v0, $v1
    beqz $v1, @wrap
    nop
    sb $v0, -0xcd2($s3)
    lhu $a0, -0xcd0($s3)
    nop
    addu $a0, $a0, $s2
    b @ret
    sh $a0, -0xcd0($s3)
@wrap:
    lbu $v0, -0xcd1($s3)
    sb $zero, -0xcd2($s3)
    addiu $v0, $v0, 1
    sb $v0, -0xcd1($s3)
    sh $s2, -0xcd0($s3)
@ret:
    move $t2, $s0
    lw $s0, 0($sp)
    lw $s1, 4($sp)
    lw $s2, 8($sp)
    lw $s3, 12($sp)
    lw $s4, 16($sp)
    lw $s5, 20($sp)
    lw $s6, 24($sp)
    lw $s7, 28($sp)
    j LAY_RET
    addiu $sp, $sp, 40

; ---------------------------------------------------------------- MCX_DAY
; memory card overlay (DC/MCX.BIN), save title: replaces the strcat of the time word onto the
; slot's day field ("D12 " + "Morn"), then appends the whole day field to the title (the
; caller's 64-byte buffer at its sp+0x20); the title's own digit/suffix/time strcats are
; removed (tools/build.py MCX_CODE) so the title gets the same "D12 Morn" as the slot list
MCX_DAY:
    addiu $sp, $sp, -24
    sw $ra, 16($sp)
    jal STRCAT
    sw $a0, 20($sp)
    lw $a1, 20($sp)
    jal STRCAT
    addiu $a0, $sp, 56
    lw $ra, 16($sp)
    jr $ra
    addiu $sp, $sp, 24

    .align 4
POOLS:
    .incbin pools
CLUTS:
    .incbin cluts
LETTERS:
    .incbin letters
TOKOFF:
    .incbin tokoff
TOKDATA:
    .incbin tokdata
END:
'''


def j(target):
    return struct.pack('<I', 0x08000000 | ((target >> 2) & 0x3FFFFFF))


NOP = bytes(4)


def build(token_letters, cluts, letters_blob):
    """token_letters: list (index = token id) of letter-id lists; cluts: 8 CLUT ids."""
    offs, data = [], bytearray()
    for lets in token_letters:
        offs.append(len(data))
        data += bytes([len(lets)]) + bytes(lets)
    if len(data) > 0xFFFF:
        raise SystemExit('token data too large')
    blobs = {'pools': b''.join(struct.pack('<3I', *p) for p in POOLS), 'cluts': struct.pack('<8H', *cluts), 'letters': letters_blob,
             'tokoff': struct.pack('<%dH' % len(offs), *offs) + (b'\0\0' if len(offs) % 2 else b''),
             'tokdata': bytes(data)}
    syms = dict(SYMS)
    syms['NTOK'] = len(token_letters)
    code, syms = assemble(ASM, BASE, syms, blobs)
    if BASE + len(code) > LIMIT:
        raise SystemExit('hook blob too large: %d bytes' % len(code))
    patches = [
        (0x80044A24, j(syms['BOX'])),                    # delay slot: 'andi a1,s7,0xffff' (harmless)
        (0x80045158, j(syms['CEN']) + NOP),
        (0x800453CC, j(syms['CEN_END_HOOK']) + NOP),
        (0x80045500, j(syms['LINE']) + NOP),
        (0x80045780, j(syms['LINE_END_HOOK']) + NOP),
        (0x800444F8, j(syms['LAYOUT']) + NOP),
        (0x80044160, j(0x800441E8) + NOP),               # text init: skip the SPRT setup loop
        # dialogue box: 28 grid cells per line instead of 26 (same as the page box; the grid holds
        # 28 x 13); English lines need more tokens than Japanese ones needed characters
        (0x800441F4, struct.pack('<I', 0x2402001C)),     # addiu v0, zero, 28
    ]
    # field popups (area name label etc., 0x800215xx / 0x800218F8): the text's left edge was
    # centre - strlen/2 * 6, i.e. 12 px per Shift-JIS character, while the box is sized from
    # the pixel width.  Use the pixel width (s4 holds it in the second function); the first
    # one gets the Japanese result for any length (box x + 166).
    patches += [
        (0x8002167C, NOP),                                 # no strlen (delay slot: sh v0,(s1))
        (0x80021684, struct.pack('<I', 0x266300A6)),       # addiu v1, s3, 0xa6
        (0x80021688, NOP * 5),
        (0x800216A0, NOP),                                 # (lhu v1,(s2))
        (0x800216A8, NOP * 2),                             # (subu / addiu 0xa0)
        (0x80021A9C, NOP),                                 # no strlen (delay slot: addu s0)
        (0x80021AA4, struct.pack('<2I', 0x3282FFFF, 0x00021042)),   # andi v0,s4,0xffff; srl v0,1
        (0x80021AAC, NOP * 4),
    ]
    return code, syms, patches
