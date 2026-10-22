# Translating Vampir (agent brief)

Read `BASE_RULES.md` (translation sections) and this file first. Names and terms:
`work/glossary/glossary.json` (main_characters, places, terms, villagers — each villager with
gender, age and job). The glossary wins over your own idea of a spelling.

## Your slice

`work/translation/en/slices/<slice>.json` has `rows` (translate every one), and `before` /
`after` (context only). Neighbouring slices are in the same folder; read them when a row needs
it. Write `work/translation/en/done/<slice>.json`:

```json
[{"id": "M0#7", "en": "Oh, it's "}, {"id": "M0#8", "en": ".", "note": "copula moved into #7"}]
```

One entry per row, same ids, same order. `note` only when a decision was not obvious.

## Villager text (`M?#k` rows)

Rows are *fragments* that the game joins at runtime. `used_in` shows each message that uses the
row: `«#k text»` is a fragment, `{PLAYER_NAME}` / `{PARTNER_NAME}` are inserted names (player 1 is
Christopher, player 2 Duran; the player may rename them, up to 8 letters), ` / ` is a line break,
`▼` waits for a button, `[PLAYER]` is the protagonist speaking, `[Name]` the villager.

* Fragments are concatenated exactly: put the spaces you need inside the fragments
  (`"Oh, it's "` + name + `"."`). Japanese word order often has to move: carry the words into the
  fragment before or after the name. A fragment may become punctuation only, or even `""`.
* A short fragment (`、`, `。`, `だ。`, `は、` …) is shared by many messages; your English must read
  correctly in every listed use. If one use cannot work, give the row a `variants` list:
  `"variants": [{"msg": 5188, "en": "..."}]` (msg = the number in `used_in`); that message gets its
  own copy.
* Who speaks: the villager named in `used_in` (age/gender/job in the glossary). Children talk
  like children, the landlord like a landlord. The protagonist ([PLAYER]) is a gentle, well-bred
  young vampire: polite, a little formal, never crude; with children he can be warm.
* `おじさん` / `おにいさん` from a child = "mister"; drop honorifics like さん/様 unless they carry
  meaning (`{PLAYER_NAME}様` from a servant = "my master" / "Master").

## Fitting the box

Dialogue lines are 240 px wide (≈ 44 characters of average text) and a box shows **3 lines**.
Each row starts on a new line after ` / ` and wraps at word boundaries by itself. A whole message
(up to `▼`) must fit in 3 lines; count `{PLAYER_NAME}` as 8 letters. Measure with

    python tools/fit.py "Oh, it's {PLAYER_NAME}! / Are you going to the fields? Let's go."

Write the line in full first; then compress or abbreviate if the message needs more than 3 lines.
Never drop the end of a sentence; if it still cannot fit, keep it and say so in `note`.

## Characters

Only ASCII plus ‘ ’ “ ” — – … é è ê à â ç ô û ü ï ö ä ñ É ♪ ♥ « » · can be drawn. Use ASCII `'`
and `"`. Japanese `・・・` becomes `...`; `ー`-lengthened words become natural English
(`うわーっ` "Waaah!"). Full-width digits become ASCII digits. `＜返答する＞` style menu options keep
the angle brackets: `<Answer>`.

## Report

Finish with a short report: rows examined vs rows in the slice, rows you could not verify, and
every call you were unsure of (referents you inferred, omissions you kept, variants you added).
