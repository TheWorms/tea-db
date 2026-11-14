# Format des fichiers lus par l'appli

L'appli lit le dossier `docs/` : `docs/thes.json`, `docs/redirections.json` et les images de `docs/assets/photos/catalogue/`. Les chemins de photo de `thes.json` sont relatifs à `docs/`.

## docs/thes.json

Une liste de fiches, triée par id, en JSON compact (431 thés, environ 230 Ko). Les champs marqués « parfois » sont absents quand ils sont vides.

| Champ | Présent | Valeur |
|---|---|---|
| `id` | toujours | Identifiant stable, 40 caractères au plus. Ne change jamais : l'appli s'en sert pour les favoris. |
| `nom` | toujours | Nom affiché, 30 caractères au plus (deux lignes sur une carte). |
| `nom_complet` | parfois | Nom long, quand `nom` en est une version raccourcie. |
| `famille` | toujours | `green`, `black`, `white`, `oolong`, `yellow`, `pu_erh`, `dark`, `herbal`, `matcha` ou `cold`. |
| `origine` | toujours | Région d'origine, 30 caractères au plus, ou `null` (mélanges, grades, certaines tisanes). |
| `eau_ml` | toujours | Volume de la recette, 350 ml au plus. |
| `the_g` | toujours | Dose pour `eau_ml`. |
| `temperature_c` | toujours | Température de l'eau, ou `null` pour une infusion à température ambiante. |
| `duree_s`, `duree_max_s` | toujours | Durée d'infusion en secondes (minimum et maximum). `0` pour un thé fouetté (matcha). |
| `fiabilite` | toujours | `legacy_referenced` : recette sourcée, pour ce thé ou pour son style (médiane de plusieurs maisons, voir `data/curation/styles.json`). `family_default` : estimation, à présenter comme telle. |
| `source_verifiee` | parfois | Date (AAAA-MM-JJ) de relecture de la recette sur sa page source. |
| `photo` | toujours | `assets/photos/catalogue/<id>.webp`, ou `null` tant que la photo n'est pas refaite : l'appli affiche alors sa propre vignette. |
| `photo_credit` | toujours | Crédit à afficher (60 caractères au plus), ou `null` sans photo. |
| `photo_exacte` | toujours | `true` seulement pour une vraie photo du produit. Les illustrations actuelles valent `false`. |
| `notes` | toujours | Descriptif, 300 caractères au plus. |
| `source` | toujours | Page d'où vient la recette. |
| `alias` | parfois | Autres noms du thé, dont ceux des doublons retirés. |
| `theine` | toujours | `oui`, `non` ou `inconnu`. N'afficher « sans théine » que pour `non`. |
| `precaution` | parfois | Texte à afficher pour une plante à usage médicinal. |
| `a_revoir` | parfois | La recette d'infusion ne convient pas : afficher ce texte et renvoyer au paquet. |

Dosage pour un autre volume : `the_g × volume ÷ eau_ml`, avec un volume de 350 ml au plus. Température et durée ne changent pas.

## docs/redirections.json

`{"ancien id": "id conservé"}` pour les 54 doublons retirés. Un favori enregistré sous un ancien id doit être reporté sur l'id conservé.

## Photos

`docs/assets/photos/catalogue/<id>.webp` : 1200 × 800 px (3:2), environ 100 Ko et jamais plus de 200 Ko, sans métadonnées EXIF. Le crédit par défaut est dans `data/photos.json`.
