# Word dictionary data

`dictionary.json` and `inflections.json` are tracked source files. SCons
compiles them into `addon/globalPlugins/polyglot/common/resources/dictionary.pickle`.
The JSON files are not included in the add-on package.

The Italian data lives next to them in two more tracked source files:

- `dictionary.it.json` — Italian headwords, each mapped to a part-of-speech
  abbreviation plus one or more Chinese glosses.
- `conjugation.it.tsv` — one row per conjugated form:
  `lemma<TAB>pos<TAB>tense<TAB>person<TAB>forms`.

SCons compiles both into
`addon/globalPlugins/polyglot/common/resources/dictionary.it.pickle` and
`.../conjugation.it.pickle` through `tools/compileItalianDictionary.py`.
Neither product is committed.

Copyright (C) 2025-2026 cary-rowen. Polyglot's selection, filtering,
corrections, new entries, source data files, and build tooling are distributed
under the GNU General Public License version 3 or later (`GPL-3.0-or-later`).
The incorporated clipboardEnhancement data is also authored by cary-rowen and
licensed under GPL version 3 or later. ECDICT material remains under its MIT
license; see the packaged resource notice for the complete attribution.

## Update the dictionary

Run these commands from the project root. Keep the ECDICT checkout at
`tools/resource/ECDICT`; that directory is ignored by Git.

Clone it once:

```powershell
git clone --depth 1 https://github.com/skywind3000/ECDICT tools/resource/ECDICT
```

Update an existing checkout when needed:

```powershell
git -C tools/resource/ECDICT pull --ff-only
```

Prepare entries for review:

```powershell
python tools/updateWordDictionary.py prepare
```

This writes missing lowercase headwords to the ignored
`tools/resource/candidates.json`. Review each entry, edit `definition` if
necessary, and set `approved` to `true` for entries to keep.

Apply the review:

```powershell
python tools/updateWordDictionary.py apply
```

`apply` validates the approved entries, updates `dictionary.json`, and
regenerates `inflections.json` from ECDICT's `exchange` and `lemma.en.txt`.
The inflection generator is called by `apply`; normally do not run it directly.
It does not build or install the add-on. Review the Git diff, then run:

```powershell
scons
```

## Sources

The current 122,370 headwords are assembled from:

- [clipboardEnhancement](https://github.com/nvdacn/clipboardEnhancement): 114,835 entries from
  `Dict.json` (commit `5f3ed93ca13b0658dcb01d31968ad8dcac5bf16f`)
- [ECDICT Basic](https://github.com/skywind3000/ECDICT): 7,496 reviewed entries from
  `ecdict.csv` (commit `bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b`)
- [ECDICT-ultimate](https://github.com/skywind3000/ECDICT-ultimate): 39 individually reviewed
  entries from release `1.0.0`

Routine updates use ECDICT Basic. ECDICT-ultimate is historical provenance,
not a required input. The add-on resource notice contains the source and
license attributions.
