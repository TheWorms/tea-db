# tea-db

[Français](README.md) | English

A catalogue of teas and herbal infusions in French. Each entry gives the dose, water temperature, steeping time, a short description and an illustration. It is read by the Théothèque Android app.

## Contents

| Path | Purpose |
|---|---|
| `docs/thes.json` | Catalogue read by the app: a list of entries sorted by identifier |
| `docs/redirections.json` | Old identifiers mapped to the identifier that was kept (duplicates removed) |
| `docs/assets/photos/catalogue/` | Illustrations in WebP, 1200 × 800 px, added over time (the folder is absent until there are some) |
| `data/` | Source data: master file, texts, recipes by style, verifications |
| `scripts/` | `curate.py` generates the published files; `add_photo.py` converts images |
| `tests/` | Catalogue consistency tests |
| `FORMAT.md` | Full description of the `thes.json` fields (in French) |

## How it works

A brewing recipe comes from a page published by a tea producer or merchant, given in each entry's `source` field. Teas of the same style (for example flower infusions) share a recipe computed from several houses: the median of the values, one vote per house. An entry without a sourced recipe is marked `family_default` and should be presented as an estimate.

An entry without an image has `photo` set to `null`: the app then shows its own placeholder. AI-generated illustrations are not photos of the actual product, so `photo_exacte` is `false`. Real photos (`photo_exacte` set to `true`) come from Wikimedia Commons; their author, licence and source page are listed in `data/photos.json`.

Herbal infusions with a medicinal use carry a `precaution` field. The catalogue gives no medical advice. Herbal infusions are brewed with boiling water (German Federal Institute for Risk Assessment, BfR); teas also carry a cold brew recipe (`froid` field), computed the same way from several houses.

## Usage

Read `docs/thes.json` directly, or serve the repository from static hosting. Photo paths are relative to the `docs/` folder. Field details are in [FORMAT.md](FORMAT.md).

## Contributing

`docs/thes.json`, `docs/redirections.json` and `data/teas.json` are generated: edit the sources in `data/`, then regenerate.

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

The code (`scripts/`, `tests/`) is under the MIT licence, see [LICENSE](LICENSE). The catalogue, the texts and the generated illustrations are under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), with the credit "Théothèque". Real photos keep their author's licence (CC BY-SA 3.0 or 4.0), given in the `photo_credit` field and in `data/photos.json`.

Recipes come from pages published by tea merchants and websites, cited in each entry's `source` field. Those sources, their brands, product names and texts remain the property of their authors and are not covered by this licence.
