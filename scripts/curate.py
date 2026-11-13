#!/usr/bin/env python3
"""Curation du catalogue et export pour l'appli, à relancer après chaque modification.

    python3 scripts/curate.py          # met à jour tous les fichiers générés
    python3 scripts/curate.py --check  # échoue si un fichier n'est pas à jour

Fichier maître : data/teas.json (toutes les fiches, doublons compris). Le script
retire d'abord tout ce qu'il a ajouté, puis réapplique les règles actuelles ; il
est donc idempotent et réversible.

À partir de data/curation/, data/textes/, data/photos.json et des images :
  - doublons (merges.json) : la fiche garde son id, reçoit status=merged et
    replaced_by, et sa recette devient celle de la fiche conservée ;
  - sous-familles (subfamilies.json) : copie de la recette sourcée d'une fiche
    d'ancrage vers les fiches sœurs sans recette propre (aucune valeur inventée) ;
  - styles (styles.json) : recette calculée à partir de plusieurs sources
    publiées (médianes) pour toutes les fiches d'un même style ; une recette
    sourcée propre est conservée dans legacy_recipe et sa source doit figurer
    parmi celles du style ;
  - vérifications (verifications.json) : source.checked_on des recettes relues ;
  - théine et précautions (cautions.json) ;
  - nom court, origine et descriptif (data/textes/*.json) ;
  - photos : un thé a une photo si docs/assets/photos/catalogue/<id>.webp
    existe, sinon photo = null.

Fichiers générés :
  data/teas.json          maître enrichi
  docs/thes.json          catalogue lu par l'appli (liste de fiches)
  docs/redirections.json  ancien id → id conservé, pour les doublons retirés

Limites de l'appli contrôlées (erreur = refus) : id ≤ 40, nom ≤ 30,
origine ≤ 30, notes ≤ 300, photo_credit ≤ 60, photo de 800×533 à 1600×1067 px
et ≤ 200 Ko, thes.json ≤ 1 Mo, eau ≤ 350 ml (au-delà, la recette de l'appli est
ramenée à 350 ml avec la dose réduite dans la même proportion ; le maître garde
les valeurs de la source). Aucune dépendance hors bibliothèque standard.
"""
from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import math
import statistics
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHOTO_REL = "assets/photos/catalogue"          # relatif à docs/
PHOTO_DIR = ROOT / "docs" / PHOTO_REL

LEGACY = "legacy_referenced"
FAMILY_DEFAULT = "family_default"
SUBFAMILY_DEFAULT = "subfamily_default"
STYLE_REFERENCED = "style_referenced"
CHECK_NOTE = "Valeurs relues sur la page source (lecture automatisée) ; identiques au catalogue."

# Limites de l'appli.
MAX_ID, MAX_NOM, MAX_ORIGINE, MAX_NOTES, MAX_CREDIT = 40, 30, 30, 300, 60
PHOTO_MIN, PHOTO_MAX = (800, 533), (1600, 1067)
PHOTO_MAX_BYTES = 200_000
APP_FILE_MAX_BYTES, APP_FILE_TARGET_BYTES = 1_000_000, 200_000
MAX_EAU_ML = 350

# Champs ajoutés aux fiches, dans cet ordre, après les champs d'origine.
ENTRY_FIELDS = (
    "status", "replaced_by", "merge_reason_fr", "merged_from", "merged_aliases",
    "subfamily", "style", "needs_review", "caffeine", "medicinal_caution_fr",
    "short_name", "origin_fr", "notes_fr",
)
CSV_BASE_COLUMNS = [
    "id", "name", "family", "aliases", "catalog_status", "tea_g", "water_ml",
    "temperature_c", "duration_seconds_min", "duration_seconds_max", "method",
    "reliability", "source_url", "photo_path",
]
CSV_EXTRA_COLUMNS = [
    "status", "replaced_by", "subfamily", "style", "caffeine", "medicinal_caution",
    "needs_review", "photo_credit", "checked_on", "nom_court", "origine", "notes",
]
# L'appli ne connaît que legacy_referenced et family_default. Une recette de style
# (style_referenced, médiane de sources publiées) lui est donnée comme recette
# sourcée ; une recette reprise d'un thé voisin (subfamily_default) comme estimation.
RELIABILITY_APP = {LEGACY: LEGACY, STYLE_REFERENCED: LEGACY,
                   SUBFAMILY_DEFAULT: FAMILY_DEFAULT, FAMILY_DEFAULT: FAMILY_DEFAULT}
CAFFEINE_APP = {"contains": "oui", "none": "non", "unknown": "inconnu"}
METHOD_LABELS = {"western": "Occidentale", "whisk": "À fouetter",
                 "room_temperature": "Infusion à température ambiante"}


class CurationError(Exception):
    pass


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2) + "\n"


def load_curation(root: Path = ROOT) -> dict:
    cur = root / "data" / "curation"
    textes: dict[str, dict] = {}
    for path in sorted((root / "data" / "textes").glob("*.json")):
        for tea_id, item in load_json(path).items():
            if tea_id in textes:
                raise CurationError(f"data/textes : {tea_id} défini deux fois ({path.name})")
            textes[tea_id] = item
    return {
        "merges": load_json(cur / "merges.json")["merges"],
        "subfamilies": load_json(cur / "subfamilies.json"),
        "styles": load_json(cur / "styles.json")["styles"],
        "cautions": load_json(cur / "cautions.json"),
        "verifications": load_json(cur / "verifications.json")["verifications"],
        "release": load_json(cur / "release.json"),
        "photos": load_json(root / "data" / "photos.json"),
        "textes": textes,
    }


# --------------------------------------------------------------------------- #
# Photos
# --------------------------------------------------------------------------- #
def webp_size(path: Path) -> tuple[int, int]:
    """Largeur et hauteur d'un fichier WebP, lues dans l'en-tête (VP8, VP8L, VP8X)."""
    with open(path, "rb") as fh:
        head = fh.read(40)
    if len(head) < 30 or head[:4] != b"RIFF" or head[8:12] != b"WEBP":
        raise CurationError(f"{path.name} n'est pas un fichier WebP")
    chunk, data = head[12:16], head[20:]
    if chunk == b"VP8X":
        w = int.from_bytes(data[4:7], "little") + 1
        h = int.from_bytes(data[7:10], "little") + 1
        return w, h
    if chunk == b"VP8 ":
        if data[3:6] != b"\x9d\x01\x2a":
            raise CurationError(f"{path.name} : en-tête VP8 invalide")
        w, h = struct.unpack("<HH", data[6:10])
        return w & 0x3FFF, h & 0x3FFF
    if chunk == b"VP8L":
        if data[0] != 0x2F:
            raise CurationError(f"{path.name} : en-tête VP8L invalide")
        bits = int.from_bytes(data[1:5], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    raise CurationError(f"{path.name} : format WebP inconnu ({chunk!r})")


def scan_photos(photo_dir: Path) -> dict[str, dict]:
    """Photos présentes : {id: {"width", "height", "bytes"}}, avec contrôle des limites."""
    found, errors = {}, []
    if not photo_dir.is_dir():
        return found
    for path in sorted(photo_dir.glob("*.webp")):
        w, h = webp_size(path)
        size = path.stat().st_size
        if w < PHOTO_MIN[0] or h < PHOTO_MIN[1]:
            errors.append(f"{path.name} : {w}×{h} px, minimum {PHOTO_MIN[0]}×{PHOTO_MIN[1]}")
        if w > PHOTO_MAX[0] or h > PHOTO_MAX[1]:
            errors.append(f"{path.name} : {w}×{h} px, maximum {PHOTO_MAX[0]}×{PHOTO_MAX[1]}")
        if size > PHOTO_MAX_BYTES:
            errors.append(f"{path.name} : {size // 1000} Ko, maximum {PHOTO_MAX_BYTES // 1000} Ko")
        found[path.stem] = {"width": w, "height": h, "bytes": size}
    if errors:
        raise CurationError("Photos hors limites (refaire avec add_photo.py) :\n" + "\n".join(errors))
    return found


# --------------------------------------------------------------------------- #
# Remise à l'état d'origine (avant curation)
# --------------------------------------------------------------------------- #
def _round(value: float, step: float) -> float:
    """Au multiple de step le plus proche ; à égalité, le plus bas."""
    return math.ceil(value / step - 0.5) * step


def style_recipe(style: dict) -> tuple[dict | None, list[str]]:
    """Recette d'un style (pour 250 ml) calculée à partir de ses sources, et erreurs éventuelles."""
    where = f"styles.json/{style.get('key')}"
    errors, srcs = [], style.get("sources") or []
    method = style.get("methode", "western")
    if method not in METHOD_LABELS:
        errors.append(f"{where} : methode doit valoir {', '.join(METHOD_LABELS)}")
    ambient = method == "room_temperature"
    base = style.get("eau_ml_base", 250)
    per_house: dict[str, int] = {}
    for src in srcs:
        per_house[src["maison"]] = per_house.get(src["maison"], 0) + 1
        if not str(src.get("url", "")).startswith("https://"):
            errors.append(f"{where} : source sans URL https ({src.get('the')})")
        if (src.get("dose_g") is None) != (src.get("eau_ml") is None):
            errors.append(f"{where} : dose_g et eau_ml vont ensemble ({src.get('the')})")
        elif method == "western" and src.get("eau_ml") is not None and src["eau_ml"] < 150:
            errors.append(f"{where} : dose donnée pour {src['eau_ml']} ml ({src.get('the')}) ; "
                          "une dose pour moins de 150 ml ne se transpose pas à une tasse, la laisser à null")
        for key in ("temp_c", "duree_s"):
            pair = src.get(key)
            if pair is not None and (len(pair) != 2 or pair[0] > pair[1]):
                errors.append(f"{where} : {key} doit être [min, max] ({src.get('the')})")
    if len(per_house) < 2:
        errors.append(f"{where} : il faut au moins deux maisons différentes")

    def by_house(values: list[tuple[str, float]]) -> list[float]:
        """Une voix par maison : la médiane de ses propres valeurs."""
        grouped: dict[str, list[float]] = {}
        for house, value in values:
            grouped.setdefault(house, []).append(value)
        return [statistics.median(v) for v in grouped.values()]

    temps = by_house([(x["maison"], sum(x["temp_c"]) / 2) for x in srcs if x.get("temp_c")])
    mins = by_house([(x["maison"], x["duree_s"][0]) for x in srcs if x.get("duree_s")])
    maxs = by_house([(x["maison"], x["duree_s"][1]) for x in srcs if x.get("duree_s")])
    doses = by_house([(x["maison"], x["dose_g"] * base / x["eau_ml"]) for x in srcs if x.get("dose_g")])
    checks = [("durée", mins), ("dose", doses)] + ([] if ambient else [("température", temps)])
    for label, values in checks:
        if len(values) < 2:
            errors.append(f"{where} : {label} donnée par moins de deux maisons")
    if ambient and temps:
        errors.append(f"{where} : infusion à température ambiante, temp_c doit être null")
    if errors:
        return None, errors
    t_min = int(_round(statistics.median(mins), 30))
    t_max = max(int(_round(statistics.median(maxs), 30)), t_min)
    return {
        "water_ml": base,
        "tea_g": _round(statistics.median(doses), 0.5),
        "temperature_c": None if ambient else int(_round(statistics.median(temps), 5)),
        "duration_seconds_min": t_min,
        "duration_seconds_max": t_max,
    }, []


def _reset_entry(entry: dict, family_defaults: dict) -> None:
    for key in ENTRY_FIELDS:
        entry.pop(key, None)

    recipe = entry["recipes"][0]
    if recipe.get("merged_copy_of"):
        entry["recipes"] = [copy.deepcopy(family_defaults[entry["family"]])]
    elif recipe.get("legacy_recipe"):
        entry["recipes"] = [copy.deepcopy(recipe["legacy_recipe"])]
    elif recipe["reliability"] in (SUBFAMILY_DEFAULT, STYLE_REFERENCED):
        entry["recipes"] = [copy.deepcopy(family_defaults[entry["family"]])]
    for recipe in entry["recipes"]:
        src = recipe["source"]
        if src.pop("check_note_fr", None) is not None:
            src["checked_on"] = None

    entry["image"] = None


def reset(catalog: dict) -> dict:
    cat = copy.deepcopy(catalog)
    family_defaults = {f["key"]: f["default"] for f in cat["families"]}
    for entry in cat["entries"]:
        drop = {a.casefold() for a in entry.get("merged_aliases") or []}
        entry["aliases"] = [a for a in entry["aliases"] if a.casefold() not in drop]
        _reset_entry(entry, family_defaults)
    return cat


# --------------------------------------------------------------------------- #
# Curation
# --------------------------------------------------------------------------- #
def curate(catalog: dict, cur: dict, photos: dict[str, dict]) -> dict:
    cat = reset(catalog)
    entries = cat["entries"]
    by_id = {e["id"]: e for e in entries}
    errors: list[str] = []

    def require(entry_id: str, where: str) -> dict | None:
        if entry_id not in by_id:
            errors.append(f"{where} : id inconnu « {entry_id} »")
            return None
        return by_id[entry_id]

    def is_legacy(entry: dict) -> bool:
        return entry["recipes"][0]["reliability"] == LEGACY

    for entry in entries:
        if len(entry["id"]) > MAX_ID:
            errors.append(f"id « {entry['id']} » : {len(entry['id'])} caractères, maximum {MAX_ID}")
        entry["status"] = "active"
        entry["replaced_by"] = None
        entry["merge_reason_fr"] = None
        entry["merged_from"] = []
        entry["merged_aliases"] = []
        entry["subfamily"] = None
        entry["style"] = None
        entry["needs_review"] = None

    # 1. Vérifications des recettes sourcées.
    for ver in cur["verifications"]:
        entry = require(ver["id"], "verifications.json")
        if entry is None:
            continue
        recipe = entry["recipes"][0]
        actual = {k: recipe[k] for k in ver["expected"]}
        same = all((actual[k] is None) if v is None else float(actual[k]) == float(v)
                   for k, v in ver["expected"].items())
        if recipe["reliability"] != LEGACY:
            errors.append(f"verifications.json : {ver['id']} n'est pas une recette sourcée")
        elif recipe["source"]["url"] != ver["url"]:
            errors.append(f"verifications.json : {ver['id']} source {recipe['source']['url']} ≠ page relue {ver['url']}")
        elif not same:
            errors.append(f"verifications.json : {ver['id']} valeurs {actual} ≠ page relue {ver['expected']} — à revérifier")
        else:
            recipe["source"]["checked_on"] = ver["checked_on"]
            recipe["source"]["check_note_fr"] = CHECK_NOTE

    # 2. Sous-familles.
    sub_doc = cur["subfamilies"]
    seen_members: dict[str, str] = {}
    merged_ids = {m["id"] for m in cur["merges"]}
    for sub in sub_doc["subfamilies"]:
        anchor = require(sub["anchor_id"], f"subfamilies.json/{sub['key']}")
        if anchor is None:
            continue
        if not is_legacy(anchor):
            errors.append(f"subfamilies.json/{sub['key']} : l'ancre {anchor['id']} n'a pas de recette sourcée")
            continue
        tag = {"key": sub["key"], "label_fr": sub["label_fr"], "anchor_id": anchor["id"]}
        anchor["subfamily"] = {**tag, "is_anchor": True}
        for member_id in sub["members"]:
            member = require(member_id, f"subfamilies.json/{sub['key']}")
            if member is None:
                continue
            if member_id in seen_members:
                errors.append(f"subfamilies.json : {member_id} est dans {seen_members[member_id]} et {sub['key']}")
                continue
            if is_legacy(member):
                errors.append(f"subfamilies.json/{sub['key']} : {member_id} a déjà une recette sourcée")
                continue
            if member_id in merged_ids:
                errors.append(f"subfamilies.json/{sub['key']} : {member_id} est un doublon (merges.json)")
                continue
            seen_members[member_id] = sub["key"]
            recipe = copy.deepcopy(anchor["recipes"][0])
            recipe["id"] = f"subfamily-{sub['key']}"
            recipe["reliability"] = SUBFAMILY_DEFAULT
            recipe["derived_from"] = anchor["id"]
            recipe["source"].pop("check_note_fr", None)
            recipe["source"]["checked_on"] = None
            recipe["source"]["kind"] = "subfamily_anchor"
            recipe["notes_fr"] = (
                f"Valeur de la sous-famille « {sub['label_fr']} », reprise de la fiche "
                f"{anchor['name']} ; non confirmée pour cette variété. Vérifier l’emballage."
            )
            member["recipes"] = [recipe]
            member["subfamily"] = {**tag, "is_anchor": False}

    for item in sub_doc.get("needs_review", []):
        entry = require(item["id"], "subfamilies.json/needs_review")
        if entry is None:
            continue
        if is_legacy(entry):
            errors.append(f"needs_review : {item['id']} a une recette sourcée")
            continue
        entry["needs_review"] = {"reason_fr": item["reason_fr"]}

    # 2b. Styles sourcés : médiane de plusieurs sources publiées.
    style_members: dict[str, str] = {}
    anchors = {sub["anchor_id"] for sub in sub_doc["subfamilies"]}
    for style in cur["styles"]:
        computed, problems = style_recipe(style)
        errors.extend(problems)
        if computed is None:
            continue
        for member_id in style["members"]:
            member = require(member_id, f"styles.json/{style['key']}")
            if member is None:
                continue
            if member_id in style_members:
                errors.append(f"styles.json : {member_id} est dans {style_members[member_id]} et {style['key']}")
                continue
            if member_id in seen_members:
                errors.append(f"styles.json/{style['key']} : {member_id} est aussi dans subfamilies.json")
                continue
            if member_id in anchors:
                errors.append(f"styles.json/{style['key']} : {member_id} est l'ancre d'une sous-famille, "
                              "convertir la sous-famille en style")
                continue
            legacy = None
            if is_legacy(member):
                legacy = copy.deepcopy(member["recipes"][0])
                if legacy["source"]["url"] not in {x["url"] for x in style["sources"]}:
                    errors.append(f"styles.json/{style['key']} : la source de {member_id} "
                                  f"({legacy['source']['url']}) doit figurer parmi celles du style")
                    continue
            if member_id in merged_ids:
                errors.append(f"styles.json/{style['key']} : {member_id} est un doublon (merges.json)")
                continue
            style_members[member_id] = style["key"]
            method = style.get("methode", "western")
            recipe = copy.deepcopy(member["recipes"][0])
            recipe.update(computed)
            recipe.update({
                "id": f"style-{style['key']}",
                "method": method,
                "method_label_fr": METHOD_LABELS[method],
                "temperature_note": "Ambiante" if method == "room_temperature" else None,
                "duration_seconds": computed["duration_seconds_min"]
                if computed["duration_seconds_min"] == computed["duration_seconds_max"] else None,
                "reliability": STYLE_REFERENCED,
                "style": {"key": style["key"], "label_fr": style["label_fr"],
                          "sources": [src["url"] for src in style["sources"]]},
                "source": {"url": style["sources"][0]["url"], "kind": "style_sources",
                           "checked_on": None},
                "notes_fr": (f"Recette du style « {style['label_fr']} » : médiane de "
                             f"{len(style['sources'])} sources publiées ({', '.join(sorted({x['maison'] for x in style['sources']}))})."),
            })
            recipe.pop("derived_from", None)
            recipe.pop("legacy_recipe", None)
            if legacy is not None:
                recipe["legacy_recipe"] = legacy
            member["recipes"] = [recipe]
            member["style"] = {"key": style["key"], "label_fr": style["label_fr"]}

    # 3. Doublons (après les sous-familles : le doublon copie la recette finale).
    for merge in cur["merges"]:
        old = require(merge["id"], "merges.json")
        new = require(merge["replaced_by"], "merges.json")
        if old is None or new is None:
            continue
        if old is new:
            errors.append(f"merges.json : {old['id']} remplacé par lui-même")
            continue
        if merge["replaced_by"] in merged_ids:
            errors.append(f"merges.json : {old['id']} → {new['id']} qui est lui-même un doublon (pas de chaîne)")
            continue
        if is_legacy(old):
            errors.append(f"merges.json : {old['id']} a une recette sourcée, fusion interdite")
            continue
        if old["status"] == "merged":
            errors.append(f"merges.json : {old['id']} listé deux fois")
            continue
        old["status"] = "merged"
        old["replaced_by"] = new["id"]
        old["merge_reason_fr"] = merge["reason_fr"]
        old["recipes"] = [dict(copy.deepcopy(r), merged_copy_of=new["id"]) for r in new["recipes"]]
        for r in old["recipes"]:
            r.pop("legacy_recipe", None)    # la recette d'origine reste sur la fiche conservée
        old["needs_review"] = copy.deepcopy(new["needs_review"])
        new["merged_from"].append(old["id"])
        known = {a.casefold() for a in new["aliases"]} | {new["name"].casefold()}
        for alias in [old["name"], *old["aliases"]]:
            if alias.casefold() not in known:
                known.add(alias.casefold())
                new["aliases"].append(alias)
                new["merged_aliases"].append(alias)

    # 4. Théine et précautions.
    caf = cur["cautions"]["caffeine"]
    contains, none = set(caf["contains"]), set(caf["none"])
    for entry_id in sorted(contains | none):
        require(entry_id, "cautions.json/caffeine")
    for entry_id in sorted(contains & none):
        errors.append(f"cautions.json : {entry_id} à la fois contains et none")
    med = cur["cautions"]["medicinal_caution"]
    med_ids = set(med["ids"])
    for entry_id in sorted(med_ids):
        require(entry_id, "cautions.json/medicinal_caution")
    for entry in entries:
        if entry["family"] in caf["families_contains"] or entry["id"] in contains:
            status = "contains"
        elif entry["id"] in none:
            status = "none"
        else:
            status = "unknown"
        entry["caffeine"] = {"status": status, "note_fr": caf.get("notes_fr", {}).get(entry["id"])}
        entry["medicinal_caution_fr"] = med["note_fr"] if entry["id"] in med_ids else None

    # 5. Nom court, origine, descriptif.
    textes = cur["textes"]
    for tea_id, item in sorted(textes.items()):
        entry = require(tea_id, "data/textes")
        if entry is None:
            continue
        if entry["status"] != "active":
            errors.append(f"data/textes : {tea_id} est un doublon, écrire le texte sur {entry['replaced_by']}")
            continue
        nom, origine, notes = item.get("nom"), item.get("origine"), item.get("notes")
        for label, value, limit in (("nom", nom, MAX_NOM), ("origine", origine, MAX_ORIGINE),
                                    ("notes", notes, MAX_NOTES)):
            if value is not None and len(value) > limit:
                errors.append(f"data/textes/{tea_id} : {label} de {len(value)} caractères, maximum {limit}")
        entry["short_name"] = nom if nom and nom != entry["name"] else None
        entry["origin_fr"] = origine
        entry["notes_fr"] = notes
    for entry in entries:
        entry.setdefault("short_name", None)
        entry.setdefault("origin_fr", None)
        entry.setdefault("notes_fr", None)
        if entry["status"] == "active" and len(entry["short_name"] or entry["name"]) > MAX_NOM:
            errors.append(f"{entry['id']} : nom « {entry['name']} » de plus de {MAX_NOM} caractères, "
                          "ajouter un « nom » court dans data/textes")

    # 6. Photos : docs/assets/photos/catalogue/<id>.webp, sinon pas de photo.
    pconf = cur["photos"]
    overrides = pconf.get("photos", {})
    for entry_id in sorted(set(overrides) - set(photos)):
        errors.append(f"data/photos.json : {entry_id} sans fichier {PHOTO_REL}/{entry_id}.webp")
    for entry_id in sorted(set(photos) - set(by_id)):
        errors.append(f"{PHOTO_REL}/{entry_id}.webp : aucun thé n'a cet id")
    for entry in entries:
        entry["image"] = None
        if entry["id"] not in photos:
            continue
        if entry["status"] == "merged":
            errors.append(f"{PHOTO_REL}/{entry['id']}.webp : doublon, renommer le fichier en "
                          f"{entry['replaced_by']}.webp")
            continue
        extra = overrides.get(entry["id"], {})
        credit = extra.get("credit") or pconf["credit_par_defaut"]
        if len(credit) > MAX_CREDIT:
            errors.append(f"data/photos.json/{entry['id']} : crédit de {len(credit)} caractères, maximum {MAX_CREDIT}")
        entry["image"] = {
            "path": f"{PHOTO_REL}/{entry['id']}.webp",
            "photo_credit": credit,
            "photo_exacte": bool(extra.get("exacte", False)),
            "width": photos[entry["id"]]["width"],
            "height": photos[entry["id"]]["height"],
        }


    if errors:
        raise CurationError("\n".join(errors))

    # 8. Métadonnées et statistiques.
    cat["schema_version"] = cur["release"]["schema_version"]
    cat["dataset_version"] = cur["release"]["dataset_version"]
    active = [e for e in entries if e["status"] == "active"]
    reliab = lambda e: e["recipes"][0]["reliability"]  # noqa: E731
    by_family_active: dict[str, int] = {}
    for e in active:
        by_family_active[e["family"]] = by_family_active.get(e["family"], 0) + 1
    cat["stats"].update({
        "entries_with_legacy_recipe": sum(reliab(e) == LEGACY or bool(e["recipes"][0].get("legacy_recipe"))
                                          for e in active),
        "inherited_family_only": sum(reliab(e) == FAMILY_DEFAULT for e in active),
        "legacy_recipe_count": sum(r["reliability"] == LEGACY or bool(r.get("legacy_recipe"))
                                   for e in active for r in e["recipes"]),
        "active_entries": len(active),
        "merged_entries": len(entries) - len(active),
        "subfamily_default_entries": sum(reliab(e) == SUBFAMILY_DEFAULT for e in active),
        "style_referenced_entries": sum(reliab(e) == STYLE_REFERENCED for e in active),
        "verified_recipes": sum(bool((r.get("legacy_recipe") or r)["source"].get("check_note_fr"))
                                for e in active for r in e["recipes"]),
        "aligned_on_style": sum(bool(r.get("legacy_recipe")) for e in active for r in e["recipes"]),
        "needs_review_entries": sum(e["needs_review"] is not None for e in active),
        "with_notes": sum(bool(e["notes_fr"]) for e in active),
        "with_photo": sum(e["image"] is not None for e in active),
        "active_by_family": dict(sorted(by_family_active.items())),
    })
    return cat


# --------------------------------------------------------------------------- #
# Sorties
# --------------------------------------------------------------------------- #
def app_volume(recipe: dict) -> tuple[float, float]:
    """Eau et dose affichées par l'appli. Au-delà de MAX_EAU_ML, l'eau est ramenée
    au maximum et la dose réduite dans la même proportion ; temps et température
    ne changent pas (water_scaling « linear_dose_only »)."""
    water, tea = recipe["water_ml"], recipe["tea_g"]
    if water <= MAX_EAU_ML:
        return water, tea
    if recipe.get("water_scaling") != "linear_dose_only":
        raise CurationError(f"{recipe['id']} : {water} ml, plus que les {MAX_EAU_ML} ml de l'appli, "
                            "et une dose qui ne se réduit pas en proportion")
    return MAX_EAU_ML, round(tea * MAX_EAU_ML / water, 1)


def render_app(catalog: dict) -> str:
    """docs/thes.json : liste des fiches actives au format de l'appli, triée par id,
    champs facultatifs omis quand ils sont vides, JSON sans espaces."""
    teas = []
    for e in sorted((e for e in catalog["entries"] if e["status"] == "active"), key=lambda e: e["id"]):
        r = e["recipes"][0]
        eau, dose = app_volume(r)
        nom = e["short_name"] or e["name"]
        tea = {"id": e["id"], "nom": nom}
        if e["short_name"]:
            tea["nom_complet"] = e["name"]
        tea.update({
            "famille": e["family"], "origine": e["origin_fr"],
            "eau_ml": eau, "the_g": dose, "temperature_c": r["temperature_c"],
            "duree_s": r["duration_seconds_min"], "duree_max_s": r["duration_seconds_max"],
            "fiabilite": RELIABILITY_APP[r["reliability"]],
        })
        if r["source"].get("check_note_fr"):
            tea["source_verifiee"] = r["source"]["checked_on"]
        img = e["image"]
        tea.update({
            "photo": img["path"] if img else None,
            "photo_credit": img["photo_credit"] if img else None,
            "photo_exacte": img["photo_exacte"] if img else False,
            "notes": e["notes_fr"], "source": r["source"]["url"],
        })
        seen, aliases = {nom.casefold(), e["name"].casefold()}, []
        for alias in e["aliases"]:
            if alias.casefold() not in seen:
                seen.add(alias.casefold())
                aliases.append(alias)
        if aliases:
            tea["alias"] = aliases
        tea["theine"] = CAFFEINE_APP[e["caffeine"]["status"]]
        if e["medicinal_caution_fr"]:
            tea["precaution"] = e["medicinal_caution_fr"]
        if e["needs_review"]:
            tea["a_revoir"] = e["needs_review"]["reason_fr"]
        teas.append(tea)
    text = json.dumps(teas, ensure_ascii=False, separators=(",", ":")) + "\n"
    size = len(text.encode("utf-8"))
    if size > APP_FILE_MAX_BYTES:
        raise CurationError(f"thes.json : {size} octets, l'appli refuse au-delà de {APP_FILE_MAX_BYTES}")
    return text


def render_redirections(catalog: dict) -> str:
    return dump_json({e["id"]: e["replaced_by"] for e in sorted(catalog["entries"], key=lambda e: e["id"])
                      if e["status"] == "merged"})



def render_all(root: Path = ROOT) -> tuple[dict[Path, str], dict, list[str]]:
    master = root / "data" / "teas.json"
    cur = load_curation(root)
    catalog = curate(load_json(master), cur, scan_photos(root / "docs" / PHOTO_REL))
    app_text = render_app(catalog)
    warnings = []
    size = len(app_text.encode("utf-8"))
    if size > APP_FILE_TARGET_BYTES:
        warnings.append(f"thes.json fait {size // 1000} Ko (objectif < {APP_FILE_TARGET_BYTES // 1000} Ko)")
    active = [e for e in catalog["entries"] if e["status"] == "active"]
    missing = [e["id"] for e in active if not e["notes_fr"]]
    if missing:
        warnings.append(f"{len(missing)} fiche(s) sans descriptif : " + ", ".join(missing[:10])
                        + (" …" if len(missing) > 10 else ""))
    outputs = {
        master: dump_json(catalog),
        root / "docs" / "thes.json": app_text,
        root / "docs" / "redirections.json": render_redirections(catalog),
    }
    return outputs, catalog, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="ne rien écrire ; code 1 si un fichier n'est pas à jour")
    args = parser.parse_args(argv)
    try:
        outputs, catalog, warnings = render_all(ROOT)
    except CurationError as exc:
        print(f"Erreur de curation :\n{exc}", file=sys.stderr)
        return 2

    stale = []
    for path, text in outputs.items():
        current = None
        if path.exists():
            with open(path, encoding="utf-8", newline="") as fh:  # garder les \r\n du CSV
                current = fh.read()
        if current != text:
            stale.append(path)
            if not args.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)

    s = catalog["stats"]
    app_kb = len(outputs[ROOT / "docs" / "thes.json"].encode("utf-8")) / 1000
    print(f"{s['entries']} fiches : {s['active_entries']} actives, {s['merged_entries']} doublons ; "
          f"{s['entries_with_legacy_recipe']} recettes sourcées propres ({s['verified_recipes']} revérifiées, "
          f"{s['aligned_on_style']} alignées sur leur style), {s['style_referenced_entries']} recettes de style, "
          f"{s['subfamily_default_entries']} de sous-famille, {s['inherited_family_only']} de famille ; "
          f"{s['with_notes']} descriptifs ; {s['with_photo']} photos, "
          f"{s['active_entries'] - s['with_photo']} sans photo ; thes.json {app_kb:.0f} Ko.")
    for warning in warnings:
        print(f"Attention : {warning}")
    rel = [str(p.relative_to(ROOT)) for p in stale]
    if args.check:
        if stale:
            print("Pas à jour (lancer python3 scripts/curate.py) : " + ", ".join(rel), file=sys.stderr)
            return 1
        print("Fichiers à jour.")
    else:
        print("Écrits : " + (", ".join(rel) if rel else "aucun changement"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
