# Vampir: Kyuuketsuki Densetsu (SLPS-01932) — text system notes

## Disc and memory map

* `SLPS_019.32` loads at `0x80010000` (0xB7000 bytes). BSS `0x8008DCF0–0x800C6CD8` is cleared at
  boot; `InitHeap` gets `0x800C6CDC` but the game never calls malloc.
* `0x800CB800` — one overlay at a time: `DC/OPN.BIN` (prologue), `DC/MCX.BIN` (menus/save),
  `DC/END.BIN` (ending), `M?/C/M?A.BIN` (day), `M?B.BIN` (night/hunter), `EP?.BIN`, `PR?.BIN`.
  Largest original: OPN.BIN `0x1CA84`; the next fixed load is at `0x800EE800`.
* `0x800EE800` — general load buffer. Fonts (`CM/FT?.TH4`) and `CM/CM.TH4` pass through it
  before `LoadImage`; the chapter text file `M?/C/M?.STC` is then loaded there and stays
  resident (glyph table pointer `0x800AF318` points into it). Next fixed load: `0x80122800`
  (`M?.VCT`), `0x80130800` (`M?.CPD`).
* `0x800A4730` (32 KB) is a load buffer of `0x80041924`; not free.

## Fonts

* `CM/FT1/2/3.TH4`: raw 4bpp 768×256 (no header), loaded to VRAM `(704,0,192,256)` = tpages
  `0x0B/0x0C/0x0D`. 12×12 cells, 21×21 per page, 1323 glyphs; values 0 = clear, 1/2 = ink,
  3 = drop shadow. Glyphs 0–219 are a fixed kana/Latin/punctuation set; kanji differ per chapter.
* CLUT ids per text attribute (`0x80084988`, 8×u16): `70FC 70FD 70FE 70FF 713C 713D 713E 713F`
  (VRAM 960–1008, rows 451/452). In the main palettes entry 3 (shadow) is 0 = transparent.
* tpage per font page: `0x80084978` = `0B 0C 0D`.
* Width table `0x8008444C`: one byte per glyph (all 12). The renderers already advance the pen
  by this table and use it as the SPRT width — the hook point for a VWF.

## Text pipeline

1. SJIS string → `0x800442A4(str, out)`: each 2-byte char is looked up linearly in the chapter
   table (entries `{u16 glyph, u8 sjis[2]}`, frequency order) and the table index is written
   as a nibble code (`0x80045A04`). Loop ends when the first byte of a pair is 0.
2. Nibble code (`0x800457EC`), params from the STC table header `P0 P1 P2` (set by
   `0x80045DAC`): nibble k < P[k] continues the code (k<3); TERM index = 16−P0; table index =
   code index + 1 when ≥ TERM.
3. Renderers (all build 20-byte SPRTs in `0x800AC790 + frame*4800`, counter `0x800AF62A`;
   DR_TPAGE prims in `0x800AED10 + frame*0x300`, counter `0x800AF624`; frame index
   `0x800C54CC`):
   * `0x80044478` layout one glyph into the box grid `0x800AF340` (u16 cells
     `glyph | attr<<12`, index `col*13 + line`); wraps when `x + width > maxw`.
     `0x80044758` draws the grid (scroll animation, typewriter).
   * `0x80045434(ot, ptr, phase, attr)` — one line at `(0x800AF620, 0x800AF622)`, x advances.
   * `0x80044FE8(ot, ptr, phase, attr)` — up to 24 glyphs centred on `0x800AF620`.
   * `0x80045E9C(ptr, phase)` — pixel width of an encoded string.
4. Box modes (`0x800441E8`): dialogue 26 cells × 3 lines, x 40, y 164, max width 240;
   full page 28 × 12, x 28, y 40, max width 264. `0x80045F84` clears, `0x80046040` newline,
   `0x80045F44(ptr, phase, attr)` starts a string.

## Script overlays

* Strings are NUL-terminated SJIS; a pointer table (stored in reverse string order) follows the
  bytecode. Bytecode: `0D 00 nn` print string nn (appends to the current line), `0F` newline,
  `10` wait for button, `0C` clear box, `18` print the player's name, `19` the partner's name,
  `11`/`12` player/villager speaks, `1A nn` pause nn frames (5–30; between the "・" dots of a
  trailing-off line, or before a punchline: the text continues on the same line).
* Some strings are referenced from code (`lui/addiu`), not from the table.

## STC (`M?/C/M?.STC`) — villager text, resident

Header `u32[4] = {0x0C, tab, txt, n_villagers}`.
* `0x0C`: `u32 n` + n records of 0x44 bytes: `u16 id, name[24], job[24], stats[18]`.
* `tab`: `u8 P0 P1 P2 x`, then table entries to `txt`.
* `txt`: `u32 off[N]` self-relative nibble offsets (string k starts at nibble `8k + off[k]`
  from `txt`), then the nibble strings back to back, each ending in TERM.
* M0: 2758 strings, M1: 6926, M2: 10581 (≈ 280k Japanese characters, max 21–25 per string).

## Tools

* `tools/extract_iso.py`, `tools/extract_text.py` (→ `work/source/text/*.json`), `tools/stc.py`.
* `tools/mips.py <file[@base]> dis|func|xref`, `tools/absrefs.py`.
* Emulator: `tools/emu.ps1 start|stop`, `tools/state.sh <name>` (resume-state snapshots),
  `tools/gdbdbg.py run "press circle; wait 30; shot x.png"` (GDB virtual pad + VRAM grabs,
  no window focus), `tools/gdbwatch.py r|w <addr> <len>` (watchpoints), `tools/gdbmem.py`.

## Testing with save states

The game looks up file positions once at boot and keeps them in RAM. A save state made with
one build carries that build's disc layout, so after a rebuild that moves files (any overlay
or STC that grew) loading an overlay from an old state reads the wrong sectors and the game
stalls on a black screen. The EXE and its token tables are in the state too, so any rebuild that
changes the token dictionary (most text changes) makes old states show garbled text. Use a
state only with the build that made it; after a rebuild, boot fresh and make new states.

## Memory card save title (DC/MCX.BIN)

The save routine (0x800CEE94) builds the card title with strcat in a 64-byte stack buffer
(31 full-width letters + NUL; the saved registers sit right after it, so a longer title crashes
the save). The load screen splits the title at 0x8140 separators: `[Vampir] [name ≤ 8]
[STAGEn] [day part]`; the day part is copied whole into a 16-byte field. The English title is
"Vampir Chris STAGE1 D12 Morn" (see `mcx_code` in `tools/build.py` and `MCX_DAY` in
`tools/vwf.py`). All pieces must be full-width Shift-JIS (`LETTER_ROWS`).

## Reaching later content in the emulator (test only, RAM pokes over GDB)

- Day/night "Waiting" menu (walk into your house): ring items map to face buttons: square =
  Talk (partner conversation, M?.STC), circle = Fast forward, cross = All.
- Stage 2/3: during the stage-1 prologue (PR0) write halfword 0x80096610 = 1 (or 2); the field
  that loads afterwards is Calstatt (or London).
- Player position: s32 at 0x80096810 (x) / 0x80096814 (z), 16-bit world units. Villager homes
  are in the table at 0x800AF76C (x, z pairs). Writing a home's coordinates at night starts the
  encounter with that villager.
- Main loop mode: halfword 0x8008DCF8 (0 title/new game, 1 stage, 3 load screen).
