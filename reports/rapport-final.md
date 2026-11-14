# Rapport final — enrichissement multi-sources de la Théothèque

Date de collecte : **2026-11-14**. Branche `feat/enrichissement-sources`.

## 1. Chiffres clés

- Fiches du catalogue maître : **512** (458 actives, 54 fusionnées avec redirection).
- Identifiants historiques : non vérifié (git indisponible).
- Nouvelles variétés ajoutées : **0** (crus Palais des Thés, recettes sourcées et revérifiées le 2026-11-14).
- Produits commerciaux réels (dédoublonnés) : **211** — Palais des Thés : 190, Thés de la Pagode : 21.
- Profils de préparation `manufacturer_exact` : **211/211** avec les 4 paramètres (dosage avec unité, eau, température, durée).
- Recettes de variétés : 455 sourcées (`legacy_referenced`), 3 estimées (`family_default`), présentées comme telles dans l'appli.
- GTIN vérifiés : **0** ; non vérifiés (`gtin: null`) : **211** (aucun code inventé).
- Conflits de consignes enregistrés : **1** (dont le cas Digestao, §3) ; aucune moyenne calculée.
- Photos réelles légalement réutilisables : **82** (dont 75 trouvées pour les 187 demandes de RECHERCHE_PHOTOS, 112 « introuvable »).
- Illustrations IA conservées (`photo_exacte: false`) : **265** ; fiches sans aucune photo : **111**.
- Sources inaccessibles documentées : **8** URL (pages Pagode supprimées/redirigées) — voir data/products.json.

## 2. Produits commerciaux (data/products.json, hors appli)

211 produits : 21 fiches Thés de la Pagode relues une par une (robots.txt autorise les pages produits) + 190 issus du relevé comparatif du 2026-11-14 (550 lignes relevées : Cafés Richard 44, Dammann Frères 206, Kusmi Tea 39, Palais des Thés 211, Thés de la Pagode 50). Seules les lignes avec consigne complète (température + durée + dose) deviennent des produits ; Dammann, Cafés Richard et Kusmi ne publient pas de dosage précis sur les pages relevées, leurs lignes restent dans le relevé sans valeur inventée. Mariage Frères était inaccessible.

## 3. Conflits (reports/conflicts.csv)

Cas **Digestao** : la fiche produit exacte gagne (90 °C / 200 ml / 1 sachet / 4 min, URL de la fiche 299), la valeur 95 °C / 7 min signalée pour la page pack 660 n'a pas été retrouvée à la relecture et reste enregistrée comme conflit ouvert (`ouvert_non_reproduit`) avec son URL. Aucune moyenne.

## 4. Photos (reports/photos-recherche.md, reports/images_rights.csv)

75 photos Wikimedia Commons retenues sur 187 demandes, licences PD/CC0/CC BY/CC BY-SA uniquement, vérifiées visuellement une par une ; crédits ≤ 60 caractères dans data/photos.json. 112 demandes restent « introuvable » plutôt qu'une photo approximative.

## 5. Limites de l'appli (vérifiées sur docs/thes.json et les photos)

| Élément | Constaté | Limite |
|---|---|---|
| id (max) | 40 car. | ≤ 40 | OK |
| nom (max) | 30 car. | ≤ 30 | OK |
| origine (max) | 28 car. | ≤ 30 | OK |
| notes (max) | 203 car. | ≤ 300 | OK |
| photo_credit (max) | 60 car. | ≤ 60 | OK |
| photos (347 WebP) | 1000×667 à 1200×800 px, max 185.9 Ko | 200 Ko max, 800×533 min, 1600×1067 max | OK |
| thes.json | 252.9 Ko | ≤ 1024 Ko (objectif 200 Ko) | OK |
| nombre de thés actifs | 458 | ~2000 max | OK |
| dépôt entier (hors .git/travail) | 35787.2 Ko | < 100 Mo conseillé | OK |

thes.json dépasse l'objectif de 200 Ko (252.9 Ko) : c'était déjà le cas avant la mission (242 Ko au commit racine) ; le plafond dur de 1 Mo est respecté.

## 6. Tests et reproductibilité

- `python3 scripts/curate.py --check` : OK (Fichiers à jour.)
- `python3 -m unittest discover -s tests` : OK (OK (skipped=1))
- Pipeline : `scripts/commons_search.py` → vérification visuelle → `scripts/add_photo.py` → `scripts/build_products_from_releve.py` → `scripts/curate.py` → `scripts/build_reports.py` → `scripts/build_archive.py`.

## 7. Livrables et points non résolus

Livrables construits par `scripts/build_archive.py` sous `output/` : `theotheque-donnees-enrichies.zip` (dépôt complet hors .git/travail/output), `theotheque-products.json`, `theotheque-sources.json`, `theotheque-coverage.csv`, `theotheque-rapport-final.md` ; la taille du ZIP est mesurée à la construction et imprimée dans le tableau final de `scripts/build_archive.py`.

- 112 demandes photo sans photo libre trouvée (« introuvable », liste dans reports/photos-recherche.md).
- 1 conflit ouvert non résolu (Digestao, page pack).
- 8 URL Thés de la Pagode mortes/redirigées ; thesdelapagode.com n'était lisible que page par page (lecture web), et Mariage Frères inaccessible pendant le relevé.
- Aucun GTIN vérifié (aucun inventé).
- thes.json à 252.9 Ko, au-dessus de l'objectif de 200 Ko (pré-existant).
