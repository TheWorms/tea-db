# tea-db

Français | [English](README.en.md)

Catalogue de thés et de tisanes en français : pour chaque fiche, la dose, la température de l'eau, la durée d'infusion, une courte description et une illustration. Il est lu par l'application Android Théothèque.

## Contenu

| Chemin | Rôle |
|---|---|
| `docs/thes.json` | Catalogue lu par l'appli : une liste de fiches triée par identifiant |
| `docs/redirections.json` | Anciens identifiants vers l'identifiant conservé (doublons retirés) |
| `docs/assets/photos/catalogue/` | Illustrations au format WebP, 1200 × 800 px, ajoutées au fur et à mesure (dossier absent tant qu'il n'y en a pas) |
| `data/` | Données sources : fichier maître, textes, recettes par style, vérifications |
| `scripts/` | `curate.py` génère les fichiers publiés ; `add_photo.py` convertit les images |
| `tests/` | Tests de cohérence du catalogue |
| `FORMAT.md` | Description complète des champs de `thes.json` |

## Principe

Une recette d'infusion vient d'une page publiée par un producteur ou un marchand de thé, indiquée dans le champ `source` de chaque fiche. Les thés d'un même style (par exemple les tisanes de fleurs) partagent une recette calculée à partir de plusieurs maisons : la médiane des valeurs, une voix par maison. Une fiche sans recette sourcée est marquée `family_default` et doit être présentée comme une estimation.

Une fiche sans image a `photo` à `null` : l'appli affiche alors sa propre vignette. Les illustrations générées par IA ne sont pas des photos du produit : `photo_exacte` vaut `false`. Les vraies photos (`photo_exacte` à `true`) viennent de Wikimedia Commons ; leur auteur, leur licence et leur page d'origine sont dans `data/photos.json`.

Les tisanes à usage médicinal portent un champ `precaution`. Le catalogue ne donne aucun avis médical.

## Utilisation

Lire `docs/thes.json` directement, ou une fois le dépôt publié sur un hébergement statique. Les chemins de photo sont relatifs au dossier `docs/`. Le détail des champs est dans [FORMAT.md](FORMAT.md).

## Contribuer

Les fichiers `docs/thes.json`, `docs/redirections.json` et `data/teas.json` sont générés : on modifie les sources dans `data/`, puis on régénère.

```bash
python3 scripts/curate.py          # régénère les fichiers publiés
python3 scripts/curate.py --check  # vérifie qu'ils sont à jour
python3 -m unittest discover -s tests
```

Où modifier :

- noms courts, origines et descriptions : `data/textes/*.json` ;
- recettes par style : `data/curation/styles.json`. Chaque source est une page publiée (maison, thé, adresse, dose, température, durée), avec au moins deux maisons par style. Ne jamais inventer une valeur ni recopier une source qu'on n'a pas lue ;
- doublons, vérifications, précautions : `data/curation/`.

Le script refuse un catalogue qui dépasse les limites de l'appli : identifiant 40 caractères, nom 30, origine 30, description 300, crédit photo 60, volume d'eau 350 ml, image 200 Ko, `thes.json` 1 Mo. Un identifiant ne se supprime ni ne se renomme jamais, car l'appli s'en sert pour les favoris ; un doublon se déclare dans `data/curation/merges.json`.

### Images

En paysage 3:2, au moins 800 × 533 px, nommées `<id>.png`, montrant le produit sec tel qu'il est vendu avec la tasse ou le verre infusé à côté, sans marque, emballage, texte ni personne. Une tisane ne contient jamais de feuilles de thé, un matcha est une poudre.

```bash
python3 scripts/add_photo.py --lot travail/   # recadre, réduit, convertit en WebP
python3 scripts/curate.py
```

Le dossier `travail/` est ignoré par git.

## Licences

Le code (`scripts/`, `tests/`) est sous licence MIT, voir [LICENSE](LICENSE). Le catalogue, les textes et les illustrations générées sont sous licence [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.fr), avec le crédit « Théothèque ». Les vraies photos gardent la licence de leur auteur (CC BY-SA 3.0 ou 4.0), indiquée dans le champ `photo_credit` et dans `data/photos.json`.

Les recettes viennent de pages publiées par des marchands et des sites de thé, citées dans le champ `source` de chaque fiche. Ces sources, leurs marques, leurs noms de produits et leurs textes restent la propriété de leurs auteurs et ne sont pas couverts par cette licence.
