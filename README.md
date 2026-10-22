# Vampir: Kyuuketsuki Densetsu — translation project

An open toolchain for translating **Vampir: Kyuuketsuki Densetsu** (ヴァンピール 吸血鬼伝説,
PlayStation, Artdink 1999, **SLPS-01932**), plus the English translation built with it.

## Contribute

All of the game's text is translated, but the game has not been played through to the end in
English yet. Bug reports, proofreading and playtesting are very welcome. Join the Discord:

**[discord.gg/MssepShjmB](https://discord.gg/MssepShjmB)**

## Play it

The latest release is **[v0.6.0](https://github.com/retro-trans/Vampir/releases/tag/v0.6.0)**:
every villager conversation in Medoekia, Calstatt and London, the story scenes, menus, memory
card screens and the graphics with Japanese text, drawn with a new variable-width font.
See [CHANGELOG.md](CHANGELOG.md) for what has been checked in-game.

### What you need

Your own dump of the Japanese disc (Redump "Vampir - Kyuuketsuki Densetsu (Japan)"), as
BIN/CUE with one file per track:

| File | SHA-256 |
|---|---|
| `Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin` | `32381c58de0d9fa79cc3b64397f2a8da03111e9e1af28edfc51bc546e74efc4e` |
| `Vampir - Kyuuketsuki Densetsu (Japan) (Track 2).bin` | `09d9237b71348e8bc480529bf9f798fa1a05361634f8df31ff5ef42a42f3405b` |

The patch changes **Track 1 only** (it gets bigger). Track 2 (audio) and the `.cue` file stay
as they are.

### Apply

**The easiest way:** [Retro Trans](https://github.com/retro-trans/retro-trans-tools) provides a
desktop interface for applying translation patches. Download the app from its Releases page,
choose the **Automatic** tab, select your Track 1 `.bin`, wait for the app to analyze it, then
click Patch.

**Other ways:** [DeltaPatcher](https://github.com/marco-calautti/DeltaPatcher) accepts the same
`.xdelta` file. Select your Track 1 `.bin` as the original file.

**Command line:** get [xdelta3](https://github.com/jmacd/xdelta), then:

```
xdelta3 -d -s "Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin" Vampir-Track1-English-v0.6.0.xdelta "Track 1 English.bin"
```

**Then assemble the disc:** put the patched Track 1 in a new folder together with copies of the
original Track 2 `.bin` and `.cue`, and give the patched file the Track 1 name that the `.cue`
expects (`Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin`). Open the `.cue` in your
emulator. Keep your original files.

A `.chd` must be unpacked to BIN/CUE first (`chdman extractcd`); multi-track CHD input is not
handled automatically. If a patcher reports a checksum mismatch, check your Track 1 against the
hash above.

Save states made with one version do not work with another (the game caches file positions);
memory card saves do.

## How it works

* [docs/TEXT_SYSTEM.md](docs/TEXT_SYSTEM.md) — disc layout, text encoding, script bytecode,
  villager text (STC), memory card title, testing notes.
* [docs/VWF.md](docs/VWF.md) — the variable-width font hooks and the 4x font atlas.
* [docs/TRANSLATING.md](docs/TRANSLATING.md), [docs/AGENT_SLICE.md](docs/AGENT_SLICE.md) —
  translation conventions and the slice workflow.
* [work/glossary/glossary.json](work/glossary/glossary.json) — names and terms.
* [docs/STANDARD_RELEASES.md](docs/STANDARD_RELEASES.md) — how releases are built and published.

The tools are Python 3 (Pillow, NumPy, Capstone). With the original files extracted to
`work/source/` (`tools/extract_iso.py`) and the translation working files in place,
`python tools/build.py --version X.Y.Z` writes the English disc to `work/output/X.Y.Z/`.
Japanese source text is never committed; the repository holds the English (`*.en.json`)
copies only.

## Credits and license

Translation and tools by binhlt0402 and the Retro Trans contributors. The in-game font is
[Noto Sans](tools/fonts/noto-sans) (SIL Open Font License). Tools are released under the
[MIT License](LICENSE). Vampir: Kyuuketsuki Densetsu is © 1999 Artdink; no game data is
included in this repository or its releases.
