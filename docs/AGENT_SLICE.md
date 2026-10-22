# Slice job (translation agent)

You translate the Japanese PS1 game "Vampir: Kyuuketsuki Densetsu" (Artdink, 1999) into English.
Working directory: `E:\Projects\Vampir`. Your prompt names ONE slice `<S>`.

1. Read `docs/TRANSLATING.md` (the brief) and the translation sections of `BASE_RULES.md`; follow both.
2. Read `work/glossary/glossary.json` (names, terms, villagers with gender/age/job).
3. Read `work/translation/en/slices/<S>.json`; translate every entry in `rows`.
   Context: `before`/`after`, neighbouring slices in the same folder, and already translated
   neighbours in `work/translation/en/done/` (stay consistent with their wording and with any
   shared fragment they already fixed). `work/translation/en/reports/followups.md` lists open
   cross-slice decisions — honour the ones that touch your rows.
   Chapter 3 (M2, London) villager text is close to its file size limit: prefer concise wording
   (no padding, no extra words the Japanese does not have).
4. Check fit with `python tools/fit.py "..."` for any message that may need more than 3 box lines.
5. Write `work/translation/en/done/<S>.json` (UTF-8 JSON array, one object per row, same ids and
   order: `{"id", "en", "note"?, "variants"?}`).
   Villager slices (`M?_C_M?_STC_*`): then run `python tools/check.py <S>`. It assembles every
   message that uses your rows (with the translated neighbours) and lists boxes over 3 lines and
   bad joins; fix your rows and run it again until none of the problems are caused by your rows.
   `<p>` in a context is a pause (script `1A nn`): the text goes on in the same line, and a
   space after a pause is added automatically. A lone "・" fragment is "." (three make "...").
   `python tools/msg.py M2#1234` prints every message that uses a row, fragment by fragment with
   the current English of the neighbours (set PYTHONIOENCODING=utf8).
6. Write your report to `work/translation/en/reports/<S>.md`: rows examined vs rows in slice, rows
   you could not verify, every uncertain call (referents inferred, omissions kept, variants added,
   fit problems), and any dependency on a row in another slice (give both row ids and the wording
   that other row needs).

Story overlay slices (`DC_*`, `M?_C_M?A_BIN_*`, `EP*`, `PR*`): rows are whole script strings in
script order; a multi-line speech is often stored with its lines in reverse order, so rebuild the
reading order from neighbours and keep each English row aligned with its own Japanese row. Several
rows can be printed on one line.

Edit no files other than the two you write, and put only your own slice's rows in your done file
(a change to another slice's row goes in your report as a dependency). Other agents run at the same time and share the
scratchpad: name any helper script or temp file after your slice (e.g. `<S>_fix.py`). Your final message is ONE short sentence (slice, rows done, number of open cross-slice dependencies); everything else goes in the report file.
