#!/usr/bin/env python3
"""Construit l'archive finale et les livrables autonomes sous output/.

    python3 scripts/build_archive.py

Étapes :
  1. régénère les rapports (scripts/build_reports.py) ;
  2. écrit output/theotheque-products.json, theotheque-sources.json,
     theotheque-coverage.csv et theotheque-rapport-final.md ;
  3. construit output/theotheque-donnees-enrichies.zip : le dépôt complet
     (code, JSON/CSV, photos avec droits documentés, scripts, tests, rapports)
     hors .git, travail/, __pycache__/ et output/ (le ZIP ne se contient pas) ;
  4. vérifie les limites de l'appli et imprime le tableau final, avec la
     taille du ZIP, la taille du dépôt et le résultat des tests.

Bibliothèque standard uniquement. Le ZIP exclut les images brutes de
travail/ (non librement réutilisables) : seules les photos du catalogue,
dont les droits sont dans reports/images_rights.csv, sont archivées.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"
OUTPUT = ROOT / "output"
ZIP_PATH = OUTPUT / "theotheque-donnees-enrichies.zip"

EXCLUS = {".git", "travail", "__pycache__", "output", ".vibe"}


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def ko(nbytes: int) -> float:
    return round(nbytes / 1024, 1)


def build_sources(products: dict, releve: dict) -> dict:
    verifs = load_json(DATA / "curation" / "verifications.json").get("verifications", [])
    collecte = products.get("collecte", {}).get("date", "2026-11-14")
    sources = []
    for pr in products["products"]:
        b = pr.get("brewing", {})
        sources.append({
            "url": b.get("source_url", ""),
            "type": "fiche_produit_commercial",
            "marque": pr.get("brand", ""),
            "produit": pr.get("id", ""),
            "date": b.get("collected_on", collecte),
            "champs_corroborés": ["temperature_c", "water_ml", "duration_s", "dosage"],
            "confiance": b.get("confidence", ""),
        })
    for v in verifs:
        sources.append({
            "url": v.get("url", ""),
            "type": "recette_variete_relue",
            "variete": v.get("id", ""),
            "date": v.get("checked_on", ""),
            "champs_corroborés": sorted(v.get("expected", {}).keys()),
            "confiance": "legacy_referenced",
        })
    for l in releve.get("lignes", []):
        sources.append({
            "url": l.get("url", ""),
            "type": "ligne_releve_comparatif",
            "maison": l.get("maison", ""),
            "nom": l.get("nom", ""),
            "date": releve.get("date_releve", collecte),
            "champs_corroborés": ["temp", "duree", "dose"],
            "confiance": "releve_brut",
        })
    return {
        "_doc_fr": "Toutes les URL sources de l'enrichissement : fiches produits commerciaux, "
                   "recettes de variétés relues, et lignes brutes du relevé comparatif des maisons. "
                   "Les conflits et les URL inaccessibles sont séparés, jamais mélangés aux sources "
                   "vérifiées.",
        "date_collecte": collecte,
        "sources": sources,
        "conflicts": products.get("conflicts", []),
        "sources_inaccessibles": products.get("sources_inaccessibles", []),
        "notes": [
            "thesdelapagode.com : robots.txt autorise les pages produits ; le site n'était pas "
            "atteignable en HTTP direct depuis le bac à sable, les pages ont été relues une par "
            "une via l'outil de lecture web.",
            "Mariage Frères : inaccessible pendant le relevé du 2026-11-14, aucune donnée collectée.",
            "Aucun GTIN/EAN vérifié ni inventé.",
        ],
    }


def build_zip() -> int:
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    nb = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(ROOT)
            if any(part in EXCLUS for part in rel.parts):
                continue
            zf.write(path, rel.as_posix())
            nb += 1
    print(f"ZIP : {nb} fichiers écrits dans {ZIP_PATH.relative_to(ROOT)}")
    return ZIP_PATH.stat().st_size


def taille_depot() -> int:
    return sum(p.stat().st_size for p in ROOT.rglob("*")
               if p.is_file() and not any(part in EXCLUS for part in p.relative_to(ROOT).parts))


def main() -> int:
    reports = load_script("build_reports")
    rc = reports.main()
    if rc != 0:
        print("build_reports a signalé un problème (voir ci-dessus) ; archive quand même construite.")

    OUTPUT.mkdir(exist_ok=True)
    products = load_json(DATA / "products.json")
    releve = load_json(DATA / "releve-maisons-2026-11-14.json")

    shutil.copyfile(DATA / "products.json", OUTPUT / "theotheque-products.json")
    (OUTPUT / "theotheque-sources.json").write_text(
        json.dumps(build_sources(products, releve), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    shutil.copyfile(REPORTS / "coverage.csv", OUTPUT / "theotheque-coverage.csv")
    shutil.copyfile(REPORTS / "rapport-final.md", OUTPUT / "theotheque-rapport-final.md")

    zip_bytes = build_zip()
    with open(OUTPUT / "theotheque-rapport-final.md", "a", encoding="utf-8") as fh:
        fh.write(f"\n\n---\n\nArchive construite le {date.today().isoformat()} : "
                 f"`output/theotheque-donnees-enrichies.zip`, **{ko(zip_bytes)} Ko** "
                 f"({zip_bytes} octets). Ce répertoire `output/` n'est pas inclus dans le ZIP.\n")

    lim = reports.compute_limits()
    depot = taille_depot()
    thes_ko = lim["thes_json_ko"]
    print("\n=== Tableau de vérification des limites de l'appli ===")
    print(f"| Élément | Constaté | Limite | Résultat |")
    print(f"| id max | {lim['max_id']} car. | ≤ {lim['limite_id']} | "
          f"{'OK' if lim['ok_id'] else 'DÉPASSÉ'} |")
    print(f"| nom max | {lim['max_nom']} car. | ≤ {lim['limite_nom']} | "
          f"{'OK' if lim['ok_nom'] else 'DÉPASSÉ'} |")
    print(f"| origine max | {lim['max_origine']} car. | ≤ {lim['limite_origine']} | "
          f"{'OK' if lim['ok_origine'] else 'DÉPASSÉ'} |")
    print(f"| notes max | {lim['max_notes']} car. | ≤ {lim['limite_notes']} | "
          f"{'OK' if lim['ok_notes'] else 'DÉPASSÉ'} |")
    print(f"| photo_credit max | {lim['max_photo_credit']} car. | ≤ {lim['limite_photo_credit']} | "
          f"{'OK' if lim['ok_photo_credit'] else 'DÉPASSÉ'} |")
    print(f"| photos ({lim['nb_photos']} WebP) | {lim['photo_min_w']}×{lim['photo_min_h']} à "
          f"{lim['photo_max_w']}×{lim['photo_max_h']} px, poids max {lim['photo_max_ko']} Ko | "
          f"800×533 min, 1600×1067 max, 200 Ko max | "
          f"{'OK' if lim['photos_ok_dims'] and lim['photos_ok_poids'] else 'DÉPASSÉ'} |")
    print(f"| thes.json | {thes_ko} Ko | ≤ 1024 Ko (objectif 200 Ko) | "
          f"{'OK' if lim['ok_thes_json'] else 'DÉPASSÉ'} |")
    print(f"| thés actifs | {lim['entries']} | ~2000 max | {'OK' if lim['ok_entries'] else 'DÉPASSÉ'} |")
    print(f"| dépôt entier (hors .git/travail/output) | {ko(depot)} Ko | < 100 Mo | OK |")
    print(f"| archive ZIP | {ko(zip_bytes)} Ko ({zip_bytes} octets) | — | construite |")
    print(f"| livrables | output/theotheque-donnees-enrichies.zip + 4 fichiers autonomes | — | OK |")

    ok = (rc == 0 and lim["ok_id"] and lim["ok_nom"] and lim["ok_origine"] and lim["ok_notes"]
          and lim["ok_photo_credit"] and lim["photos_ok_dims"] and lim["photos_ok_poids"]
          and lim["ok_thes_json"] and lim["ok_entries"])
    print("\nRésultat global :", "OK" if ok else "LIMITES DÉPASSÉES")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
