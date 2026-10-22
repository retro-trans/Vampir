# VWF and sharp font (build 0.1.0)

See `docs/TEXT_SYSTEM.md` for how the original text system works.

## Tokens instead of glyphs

The game addresses up to 1323 "glyphs" through the chapter table (STC) and a width table
(`0x8008444C`, one byte per glyph). In the English build a glyph is a **token** — a single
letter (ids 0x00–0x9F = font letter id) or a multi-letter piece learned from the script
(`tools/vtext.py`, BPE merges inside words; the space is its own token 0x20). Tokens keep the
game's layout logic working unchanged (one grid cell per token, width = sum of letter
advances) and compress the text: the villager text (STC) costs about the same bytes in English
as it did in Japanese.

Runtime-encoded strings (script overlays, EXE UI, villager names) store 2-byte token codes:
full-width Shift-JIS for single letters (so the name entry, the player's name and numbers keep
working) and the user-defined area F040+ for the other tokens.

## Drawing

`tools/vwf.py` assembles the hooks into an EXE extension at `0x800C6E00` (the EXE is grown;
the BSS ends at 0x800C6CD8 and the game never uses its heap).

* `EMIT(token, x, y, attr, h, vtop)` draws each letter of a token as a POLY_FT4 (40 bytes)
  sampling the 4x atlas; `vtop`/`h` crop the top line during the box scroll animation.
  Quads come from three pools (254 per frame, double-buffered): the game's SPRT and DR_TPAGE
  text buffers, which the hooks no longer use, and free kernel RAM at 0x8000B800.
* Hooks: dialogue grid `0x80044A24`, centred line `0x80045158` (+ end `0x800453CC`), line
  `0x80045500` (+ end `0x80045780`); the end hooks skip linking when nothing was drawn.
* Layout `0x800444F8`: word wrap — at a space, the width and the token count of the following
  word are measured by decoding ahead (the decoder state is saved/restored) and the line breaks
  there if the word would not fit in the pixels or in the grid cells left on the line; a column
  guard prevents overrunning the 13-line x 28-column grid.
* `0x800441F4`: the dialogue box gets 28 grid cells per line (was 26, as the page box has).
  An English line of 240 px can need more tokens than the 26 characters a Japanese line had;
  without this the column guard broke such lines inside a word.
* `0x80044160`: the text init no longer rewrites the SPRT buffer (now quad memory).

## Font texture

`tools/font_atlas.py`: Noto Sans (OFL), 11 px em, 12 px line. Letters are rasterised at 4x
(48-texel cells, 16 coverage levels) into the 768x256 4bpp texture that replaces
`CM/FT1-3.TH4` (VRAM 704,0, three 256x256 pages). The top-left texel of each 4x4 block holds the
1x rasterisation, which is what a native-resolution GPU samples. Eight 16-entry CLUTs (one per
text attribute colour, ramped from black) live in page 0 rows 248–249. No texture replacement
packs are used.

## Name entry

The 90-cell grid string in OPN.BIN is rewritten in place with Latin letters (A–Z, a–z, digits,
punctuation, accents); the last two cells are "OK". Names stay 8 letters (the original limit);
the default names are "Chris" and "Duran", stored letter by letter.
