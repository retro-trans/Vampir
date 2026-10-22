# Change log

## 0.6.0 — first public release (2026-10-22)

First published English patch: everything in 0.1.0 and 0.1.1 below.

- All game text is translated: the villager conversations of all three stages (Medoekia,
  Calstatt, London), the story scenes, menus, the memory card screens and the name entry. Text
  baked into graphics is redrawn in English (title logo, opening subtitles, menu buttons, save
  prompt, credit role titles).
- New variable-width Latin font integrated into the game (no emulator texture replacement).
- Checked in-game: opening, title, new game, prologue, Medoekia day and night, menus, partner
  conversation, night encounter, nightfall save prompt, saving and loading, Calstatt field.
  Not yet played through: the rest of Calstatt and London, and the endings (their text passes the
  automatic fit checks).
- Patch: Track 1 only (raw MODE2/2352 `.bin`); Track 2 (audio) and the CUE sheet are unchanged.

## 0.1.1 — local build (included in 0.6.0)

- Field popups (area name label such as "Medoekia", "Harbor St."): the text is now centred in its
  box. The game placed the text at `centre - characters × 6` (12 px per Japanese character) but sized
  the box from the pixel width, so English names started left of the box. It now uses the
  pixel width (EXE patches at 0x8002167C and 0x80021A9C in `tools/vwf.py`).

## 0.1.0 — first local English build (included in 0.6.0)

### Engine
- Variable-width Latin font integrated into the game's own text renderers. Every glyph is now a
  token of one or more letters; each letter is drawn as a POLY_FT4 from a 4x texel-density Noto
  Sans atlas (11 px em on screen, 48-texel cells), so upscaling emulators show sharp text. The
  top-left texel of each 4x4 block holds the 1x rasterisation for native-resolution rendering.
  Texture 768x256 4bpp (three 256x256 pages, under the 1024 px limit); no emulator texture
  replacement is used.
- Hooks (`tools/vwf.py`, EXE extension at 0x800C6E00): shared quad emitter, the dialogue grid,
  the single-line and centred-line renderers, safe linking when a string draws nothing, and a
  layout hook that adds word wrap (break at the space before a word that does not fit) plus a
  guard against overrunning the grid columns. Letter quads come from three pools (254 per frame,
  double-buffered): the game's old SPRT/DR_TPAGE text buffers and free kernel RAM at 0x8000B800,
  so the chapter STC may grow up to 0x34000 bytes.
- Word wrap also counts grid cells: a word that would overrun the cells left on the line moves
  to the next line, and the dialogue box line has 28 cells instead of 26. Fixes lines that were
  broken inside a word ("he t / ried"). `tools/fit.py` models the same rule.
- Own 16-level CLUTs per text colour, embedded in the font texture.
- Token dictionary built from the English script (BPE merges inside words); widths written to
  the game's width table, so centring and wrapping use real widths.
- Villager text (`M?.STC`) rebuilt: English names/jobs, new frequency table and nibble-code
  parameters chosen for the smallest size, strings re-encoded. Per-message variants of shared
  fragments are supported by repointing `0D` string references in the villager scripts (`M?.SQC`).
- Script overlays and EXE strings relocated (pointer tables and lui/addiu pairs repointed).
  Strings that do not fit in place go to a pool at the top of the overlay window, ending at
  0x800ED800 (the gap after the original file is loaded as zeros). Fixes a hang on entering the village: strings appended right after the file had
  overwritten the overlay's runtime data (0x800D9DB0 with M0A loaded), which led to a crash
  that wiped the BIOS exception handler.
- Name entry: Latin letter grid (upper/lower case, digits, punctuation, accents), default names
  "Chris" and "Duran" stored letter by letter (8-letter limit of the original screen).
- Memory card save title: kept as full-width letters with 0x8140 separators (the BIOS browser
  shows Shift-JIS only). Morning/Evening are stored letter by letter too (they showed as garbage
  in the card manager).
- Fix: saving crashed the game (address error in the BIOS exception handler). The title is built
  with strcat in a 64-byte stack buffer (31 full-width letters), and "Vampir(1) Chris STAGE1 Day 1
  Evening" overran it into the saved registers. The new format is "Vampir Chris STAGE1 D12 Morn"/"Eve"
  (31 letters at most with an 8-letter name). The slot number is dropped, and the slot list's day
  field starts with a full-width D (MCX.BIN code patches in `tools/build.py`). The title copies the
  finished day field (`MCX_DAY` hook), so the load screen parser still finds its three separators.
- Memory card messages: "The game will continue." / "The game will now resume." are full sentences
  now, because they also follow "Save completed successfully." (the "..., so" first lines became
  "The Memory Card was removed." / "An error occurred.").
- Graphics re-rendered in English: opening subtitle strips (DOP.DAT), Rose poem strips (DD3, DED,
  LDN.DAT), title logo "Vampir" and subtitle "Legend of the Vampire" (OPN.DAT), menu and status
  button labels and the save-prompt "Vampir" logo in CM.TH4, staff credit role titles in ST.DAT (staff names are kept as in the
  original) (`tools/gfx.py`, specs in `work/ui/gfx_text.json`, `work/ui/cm_labels.json`).
- Disc builder gives the EXE, the overlays and the STC files fixed places with fixed capacity
  at the end of Track 1, so file positions (cached by the game at boot) stay the same between
  builds and save states keep working.
- Disc builder grows Track 1 as needed and moves `DUMMY.DA` with the audio track.

### Translation
- The whole game is translated: story scripts (opening, prologues, day scenes, endings, memory
  card menu, ending credits), EXE UI, all three chapters of villager conversations (Medoekia,
  Calstatt, London: about 20,000 text fragments) and the names and jobs of all 300 residents.
  Each chapter had a reconcile pass for cross-fragment wording.
- Villager script pauses (`1A nn`) are now understood: a message continues across a pause, and
  a space is added automatically after a pause in English (`tools/auto_space.py`). A lone "・"
  fragment between pauses is ".", so three make "...".
- Variants can target one occurrence (`{"ref": position of the string reference}`) or a whole
  message (`{"msg": message position}`); the automatic fixes use single occurrences, so repeated
  fragments such as the "・" dots of a pause are no longer all changed at once.
- Automatic fixes also drop the "." that follows an ellipsis and put ", " before the player name.
- `tools/check.py <slice>` checks only the messages that use a slice's rows; agents run it.
- `tools/msg.py` shows every message that uses a row, fragment by fragment.
- A deliberately empty translation (e.g. an honorific after the player name) is now written as an
  empty string; before it was treated as untranslated and shown as a `[#k]` placeholder.
- M1 (Calstatt) reconcile pass: cross-slice dependencies resolved (fixes/M1_reconcile_A/B.json).
- `tools/refresh.sh` merges translations, fixes names, adds pause spaces and checks the text.
- Glossary of the main cast, hunters, places, game terms and all 208 residents (gender and age
  from the game data).
- Translation pipeline: 80-row slices with full message context reconstructed from the scripts
  (speaker, inserted names, line breaks), fit checker for the 3-line dialogue box.
