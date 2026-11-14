# tea-db

[Français](README.md) | English

**Browse the catalogue online: [theworms.github.io/tea-db](https://theworms.github.io/tea-db/?lang=en)**

A catalogue of teas and herbal infusions in French. Each entry gives the dose, water temperature, steeping time, a short description and an illustration. It is read by the Théothèque Android app.

## Contents

| Path | Purpose |
|---|---|
| `docs/thes.json` | Catalogue read by the app: a list of entries sorted by identifier |
| `docs/redirections.json` | Old identifiers mapped to the identifier that was kept (duplicates removed) |
| `docs/index.html` | Catalogue browsing page (`app.js`, `volume.js`, `catalogue.js`) |
| `docs/assets/photos/catalogue/` | Illustrations in WebP, 1200 × 800 px, added over time (the folder is absent until there are some) |
| `data/` | Source data: master file, texts, recipes by style, verifications |
| `scripts/` | `curate.py` generates the published files; `add_photo.py` converts images |
| `tests/` | Catalogue consistency tests (Python) and page tests (Node.js) |
| `FORMAT.md` | Full description of the `thes.json` fields (in French) |

## How it works

A brewing recipe comes from a page published by a tea producer or merchant, given in each entry's `source` field. Teas of the same style (for example flower infusions) share a recipe computed from several houses: the median of the values, one vote per house. An entry without a sourced recipe is marked `family_default` and should be presented as an estimate.

An entry without an image has `photo` set to `null`: the app then shows its own placeholder. All images are real, freely licensed photos from Wikimedia Commons; their author, licence and source page are listed in `data/photos.json`. `photo_exacte` is `true` when the photo shows that very tea, and `false` when it shows a similar tea or has been retouched.

Herbal infusions with a medicinal use carry a `precaution` field. The catalogue gives no medical advice. Herbal infusions are brewed with boiling water (German Federal Institute for Risk Assessment, BfR); teas also carry a cold brew recipe (`froid` field), computed the same way from several houses.

## Usage

Read `docs/thes.json` directly, or serve the repository from static hosting. Photo paths are relative to the `docs/` folder. Field details are in [FORMAT.md](FORMAT.md).

## Browsing the catalogue

Online: **[theworms.github.io/tea-db](https://theworms.github.io/tea-db/?lang=en)**. Offline: open `index.html` at the root (or `docs/index.html`) in a browser, no server needed.

The page shows the catalogue as cards, with search and a family filter. On each entry it computes the dose for the chosen volume: 100 to 350 ml in 50 ml steps, the volumes of the BRU machine, with no preselection; the last chosen volume is remembered in the browser. When an entry has a `froid` recipe, a "Hot / Cold" choice appears; herbal infusions never have one. The page is available in French and English (only the interface is translated: names and descriptions stay in French), in light or dark theme, and each entry has its own direct link (`#identifier`). It is published by GitHub Pages from the `docs/` folder of the `main` branch.

```bash
node --test tests/volume.test.cjs   # dose calculation and volume memory
node tests/browser.cjs              # full walkthrough, with Playwright and Chromium
# Optional variables: PLAYWRIGHT_MODULE=/path/to/playwright CHROMIUM_PATH=/path/to/chromium
```

## Contributing

`docs/thes.json`, `docs/redirections.json`, `docs/catalogue.js` and `data/teas.json` are generated: edit the sources in `data/`, then regenerate.

```bash
python3 scripts/curate.py          # regenerate the published files
python3 scripts/curate.py --check  # check that they are up to date
python3 -m unittest discover -s tests
```

Where to edit:

- short names, origins and descriptions: `data/textes/*.json`;
- recipes by style: `data/curation/styles.json`. Each source is a published page (house, tea, URL, dose, temperature, time), with at least two houses per style. Never invent a value or copy a source you have not read;
- duplicates, verifications, cautions: `data/curation/`.

The script rejects a catalogue that exceeds the app's limits: identifier 40 characters, name 30, origin 30, description 300, photo credit 60, water volume 350 ml, image 200 KB, `thes.json` 1 MB. An identifier is never deleted or renamed, because the app uses it for favourites; a duplicate is declared in `data/curation/merges.json`.

### Images

Landscape 3:2, at least 800 × 533 px, named `<id>.png`, showing the dry product as sold with the brewed cup or glass beside it, with no brand, packaging, text or people. An herbal infusion never contains tea leaves, and matcha is a powder.

```bash
python3 scripts/add_photo.py --lot travail/   # crops, shrinks, converts to WebP
python3 scripts/curate.py
```

The `travail/` folder is ignored by git.

## Licences

The code (`scripts/`, `tests/`) is under the MIT licence, see [LICENSE](LICENSE). The catalogue and the texts are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with the credit "Théothèque". Photos keep their author's licence (CC0, public domain, CC BY or CC BY-SA), given in the `photo_credit` field and in `data/photos.json`.

Recipes come from pages published by tea merchants and websites, cited in each entry's `source` field. Those sources, their brands, product names and texts remain the property of their authors and are not covered by this licence.
