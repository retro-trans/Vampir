# Standard Retro Trans releases

Releases use the shared [Retro Trans release builder](https://github.com/retro-trans/retro-trans-tools/blob/main/docs/RELEASE_STANDARD.md),
so the Retro Trans app and its catalog can recognise and apply them.

Install the builder in the Python environment used for release work (Python 3.8+; the Windows
package bundles xdelta3):

```powershell
python -m pip install git+https://github.com/retro-trans/retro-trans-tools.git@v0.5.18
```

The disc is BIN/CUE with two tracks. Only Track 1 (raw MODE2/2352 data) changes; Track 2
(audio) and the CUE sheet are byte-identical to the original, so a release is a single-file
(schema v1) patch of Track 1, the same as other per-track PS1/Dreamcast releases in the
organisation.

Build the disc first (`python tools/build.py --version X.Y.Z`), then write a private
`release-local.json` outside the repository (paths are relative to the configuration file):

```json
{
  "game_id": "vampir-kyuuketsuki-densetsu",
  "game_name": "Vampir: Kyuuketsuki Densetsu",
  "platform": "PS1",
  "version": "X.Y.Z",
  "patches": [
    {
      "patch": "Vampir-Track1-English-vX.Y.Z.xdelta",
      "edition": "Japan / Track 1 raw MODE2/2352",
      "language": "en",
      "source_version": "original",
      "source_format": "bin",
      "target_format": "bin",
      "source": "../Vampir/Vampir - Kyuuketsuki Densetsu (Japan) (Track 1).bin",
      "target": "../Vampir/work/output/X.Y.Z/Vampir (English vX.Y.Z) (Track 1).bin"
    }
  ]
}
```

Add one more entry per published earlier version (`source_version` set to that version, its
exact published Track 1 as `source`) to offer smaller upgrade patches. Omit `source_commit`;
the helper pins the current clean HEAD.

```powershell
python tools/release.py X.Y.Z --config ../Vampir-release/release-local.json --dry
python tools/release.py X.Y.Z --config ../Vampir-release/release-local.json
```

The helper generates every patch, applies each to its exact source, checks the entire result's
SHA-256, and prepares `BUILD-MANIFEST.json`, `SHA256SUMS.txt` and `VALIDATION.json`.

Releases follow the SRW-Z release format. Write the notes first in
`docs/release-notes/vX.Y.Z.md`, with these sections: intro, Apply, "What's in" / "What changed
since", Testing status, What's included, How it was translated, Acknowledgements, Source code,
Contribute, and the footer. The helper uses them as the release body and generates
`README-vX.Y.Z.txt` (notes plus a source/output hash block), `CHANGELOG-vX.Y.Z.txt`,
`SHA1SUMS-vX.Y.Z.txt` and `SHA256SUMS-vX.Y.Z.txt` (all assets). The title is
"Vampir English — vX.Y.Z". It then creates the `release/vX.Y.Z` branch and `vX.Y.Z` tag, uploads
to a draft, verifies the uploaded assets and only then publishes. Existing releases are refused and
assets are never overwritten; corrected bytes need a new version.

The `Validate standard release` workflow re-checks the published assets on GitHub. The central
catalog discovers valid releases hourly.
