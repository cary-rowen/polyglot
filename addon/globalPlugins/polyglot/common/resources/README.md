# Local dictionary licensing and provenance

Polyglot ships two independent compiled dictionaries:

- `dictionary.pickle` — English-to-Chinese (English lookups only)
- `dictionary.it.pickle` — Italian-to-Chinese (Italian lookups only)

The two files are never merged at runtime: `EnglishChineseDictionary` loads only
the English bundle and `ItalianChineseDictionary` loads only the Italian one, so
a lookup in one language can never return an entry from the other.

The reviewable source files for the English dictionary are kept in
`tools/resource` in the source repository.

## English-to-Chinese (`dictionary.pickle`)

Copyright (C) 2025-2026 cary-rowen. The selection, filtering, corrections,
new entries, build tooling, and compiled dictionary are distributed under the
GNU General Public License version 3 or later (`GPL-3.0-or-later`). See
`COPYING.txt` at the root of the add-on package. The corresponding source is
available from <https://github.com/cary-rowen/polyglot>.

The dictionary incorporates material under these original licenses:

- clipboardEnhancement `Dict.json`, authored by cary-rowen, commit
  `5f3ed93ca13b0658dcb01d31968ad8dcac5bf16f`, GPL version 3 or later:
  <https://github.com/nvdacn/clipboardEnhancement/commit/5f3ed93ca13b0658dcb01d31968ad8dcac5bf16f>;
- ECDICT Basic `ecdict.csv`, commit
  `bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b`, MIT:
  <https://github.com/skywind3000/ECDICT/commit/bc015ed2e24a7abef49fc6dbbb7fe32c1dadaf8b>;
- 39 individually reviewed entries from ECDICT-ultimate 1.0.0, MIT:
  <https://github.com/skywind3000/ECDICT-ultimate/releases/tag/1.0.0>.

## Italian-to-Chinese (`dictionary.it.pickle`)

Derived from the offline Italian-Chinese dictionary `yihan.sqlite`
(意汉词典, yihan.it data, 122,436 entries), supplied by the add-on user for
personal use. Each entry keeps only a part-of-speech abbreviation and the
Chinese gloss; verb forms are mapped back to their infinitive.

- 62,756 headwords
- 246,618 verb-form aliases
- Compiled with the same `polyglot.wordDictionary` schema, version 1.

ECDICT Basic copyright (c) 2025 Linwei. ECDICT-ultimate copyright (c) 2018 Linwei.
The following MIT notice applies to the ECDICT material:

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
