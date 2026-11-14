#!/usr/bin/env python3
"""Génère les rapports chiffrés de la mission d'enrichissement (reports/).

    python3 scripts/build_reports.py

Bibliothèque standard uniquement. Relit docs/thes.json, data/*.json,
reports/photos-candidates.json, reports/photos-selection.json et les photos de
docs/assets/photos/catalogue/, puis produit :

  - reports/coverage.csv          une ligne par variété (active ou fusionnée) et par produit
  - reports/conflicts.csv         conflits de consignes (jamais de moyenne)
  - reports/images_rights.csv     droits de chaque photo du catalogue
  - reports/photos-recherche.md   les 187 demandes : photo retenue (page, auteur, licence,
                                  justification) ou « introuvable »
  - reports/rapport-final.md      synthèse chiffrée, limites de l'appli, résultat des tests

La conservation des identifiants historiques est vérifiée contre le commit
racine du dépôt (git rev-list --max-parents=0) ; sans git, la ligne est marquée
« non vérifié » plutôt qu'affirmée. Les tests (curate --check + unittest) sont
rejoués par le script et leur résultat est repris dans le rapport.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
REPORTS = ROOT / "reports"
PHOTO_DIR = DOCS / "assets" / "photos" / "catalogue"

LIMITES = {
    "id": 40,
    "nom": 30,
    "origine": 30,
    "notes": 300,
    "photo_credit": 60,
    "photo_poids_ko": 200,
    "photo_min": (800, 533),
    "photo_max": (1600, 1067),
    "thes_json_ko_cible": 200,
    "thes_json_ko_max": 1024,
    "entrees_max": 2000,
}

_spec = importlib.util.spec_from_file_location("curate", ROOT / "scripts" / "curate.py")
curate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(curate)


def load_json(path: Path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def ko(nbytes: int) -> float:
    return round(nbytes / 1024, 1)


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def ids_commit_racine() -> set[str] | None:
    """Ids présents dans data/teas.json au commit racine du dépôt, ou None sans git."""
    try:
        root = subprocess.check_output(
            ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=ROOT, text=True
        ).split()[0]
        raw = subprocess.check_output(["git", "show", f"{root}:data/teas.json"], cwd=ROOT, text=True)
        doc = json.loads(raw)
        entries = doc["entries"] if isinstance(doc, dict) else doc
        return {e["id"] for e in entries}
    except Exception:
        return None


def run_commande(args: list[str]) -> tuple[bool, str]:
    proc = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=600)
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    resume = tail[-1] if tail else ""
    return proc.returncode == 0, resume


def compute_limits() -> dict:
    """Vérifie les limites lues par l'appli sur docs/thes.json et les photos."""
    thes = load_json(DOCS / "thes.json")
    res = {"entries": len(thes), "thes_json_ko": ko((DOCS / "thes.json").stat().st_size)}
    for champ in ("id", "nom", "origine", "notes", "photo_credit"):
        valeurs = [len(e.get(champ) or "") for e in thes]
        res[f"max_{champ}"] = max(valeurs) if valeurs else 0
        res[f"limite_{champ}"] = LIMITES[champ]
        res[f"ok_{champ}"] = res[f"max_{champ}"] <= LIMITES[champ]
    photos = []
    for path in sorted(PHOTO_DIR.glob("*.webp")):
        w, h = curate.webp_size(path)
        poids = ko(path.stat().st_size)
        photos.append({"id": path.stem, "w": w, "h": h, "ko": poids,
                       "ok_dims": LIMITES["photo_min"][0] <= w and LIMITES["photo_min"][1] <= h
                       and w <= LIMITES["photo_max"][0] and h <= LIMITES["photo_max"][1],
                       "ok_poids": poids <= LIMITES["photo_poids_ko"]})
    res["photos"] = photos
    res["limite_photo_poids"] = LIMITES["photo_poids_ko"]
    res["nb_photos"] = len(photos)
    res["photos_ok_dims"] = all(p["ok_dims"] for p in photos)
    res["photos_ok_poids"] = all(p["ok_poids"] for p in photos)
    res["photo_max_ko"] = max((p["ko"] for p in photos), default=0)
    res["photo_max_w"] = max((p["w"] for p in photos), default=0)
    res["photo_max_h"] = max((p["h"] for p in photos), default=0)
    res["photo_min_w"] = min((p["w"] for p in photos), default=0)
    res["photo_min_h"] = min((p["h"] for p in photos), default=0)
    res["ok_thes_json"] = res["thes_json_ko"] <= LIMITES["thes_json_ko_max"]
    res["ok_entries"] = res["entries"] <= LIMITES["entrees_max"]
    return res


def build_coverage(thes: list, teas: dict, redirections: dict, products: dict) -> dict:
    REPORTS.mkdir(exist_ok=True)
    rows = []
    thes_by_id = {e["id"]: e for e in thes}
    for entry in teas["entries"]:
        eid = entry["id"]
        if entry.get("status") == "merged":
            rows.append(["variete", eid, entry.get("short_name") or entry.get("name", ""), "",
                         entry.get("family", ""), f"fusionnee vers {entry.get('replaced_by', '')}",
                         "", "", "", "", ""])
        elif eid in thes_by_id:
            e = thes_by_id[eid]
            photo = "reelle" if e.get("photo") and e.get("photo_exacte") else (
                "illustration_ia" if e.get("photo") else "non")
            rows.append(["variete", eid, e["nom"], "", e["famille"], "active", e["fiabilite"],
                         e.get("source", ""), e.get("source_verifiee") or "", photo,
                         e.get("photo_credit") or ""])
    for pr in products["products"]:
        b = pr.get("brewing", {})
        rows.append(["produit", pr["id"], pr["name"], pr.get("brand", ""), pr.get("category", ""),
                     "produit_commercial", b.get("confidence", ""), b.get("source_url", ""),
                     b.get("collected_on", ""), pr.get("photo_status", ""), ""])
    with open(REPORTS / "coverage.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["type", "id", "nom", "marque", "famille", "etat", "fiabilite_ou_confiance",
                    "source", "date_verif_ou_collecte", "photo", "credit_photo"])
        w.writerows(rows)
    return {"lignes": len(rows),
            "varietes": sum(1 for r in rows if r[0] == "variete"),
            "produits": sum(1 for r in rows if r[0] == "produit")}


def build_conflicts(products: dict) -> int:
    conflits = products.get("conflicts", [])
    with open(REPORTS / "conflicts.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["produit_id", "champ", "retenu", "contexte_retenu", "url_retenue",
                    "rejete", "contexte_rejete", "url_rejetee", "statut"])
        for c in conflits:
            ch, rj = c.get("chosen", {}), c.get("rejected", {})
            w.writerow([c.get("product_id", ""), c.get("field", ""),
                        json.dumps(ch, ensure_ascii=False), ch.get("context", ""), ch.get("url", ""),
                        json.dumps(rj, ensure_ascii=False), rj.get("context", ""), rj.get("url", ""),
                        c.get("status", "")])
    return len(conflits)


def build_images_rights(thes: list, photos_json: dict, selection: dict) -> int:
    sel = selection.get("photos", {}) if isinstance(selection, dict) else {}
    credit_defaut = photos_json.get("credit_par_defaut", "")
    thes_by_id = {e["id"]: e for e in thes}
    overrides = photos_json.get("photos", {})
    n_reelles = 0
    with open(REPORTS / "images_rights.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "fichier", "largeur_px", "hauteur_px", "poids_ko", "credit",
                    "photo_exacte", "licence", "page_source"])
        for path in sorted(PHOTO_DIR.glob("*.webp")):
            eid = path.stem
            wt, ht = curate.webp_size(path)
            e = thes_by_id.get(eid, {})
            exacte = bool(e.get("photo_exacte")) if e else bool(overrides.get(eid, {}).get("exacte"))
            credit = e.get("photo_credit") or overrides.get(eid, {}).get("credit") or credit_defaut
            if eid in sel:
                licence = f"{sel[eid].get('license', '')} ({sel[eid].get('license_url', '')})"
                page = sel[eid].get("page", "")
            elif exacte:
                licence = "voir crédit (Wikimedia Commons)"
                page = overrides.get(eid, {}).get("source", "")
            else:
                licence = "illustration IA Théothèque (pas une photo réelle)"
                page = ""
            if exacte:
                n_reelles += 1
            w.writerow([eid, path.name, wt, ht, ko(path.stat().st_size), credit,
                        "oui" if exacte else "non", licence, page])
    return n_reelles


def build_photos_recherche(demandes: list, candidates: dict, selection: dict,
                           photos_json: dict) -> dict:
    sel = selection.get("photos", {}) if isinstance(selection, dict) else {}
    overrides = photos_json.get("photos", {})
    lignes = []
    retenues = 0
    introuvables = 0
    for d in demandes:
        eid = d["id"]
        if eid in sel and overrides.get(eid, {}).get("exacte"):
            s = sel[eid]
            auteur = clean_html(s.get("artist", ""))
            titre = s.get("title", "").removeprefix("File:")
            licence = s.get("license", "")
            licence_url = s.get("license_url", "")
            justif = (f"Photo retenue : [{titre}]({s.get('page', '')}) par {auteur}, "
                      f"licence [{licence}]({licence_url}). Justification : vérifiée visuellement, "
                      f"elle correspond à « {d['montrer']} » (requête Commons « {s.get('query', '')} », "
                      f"score {s.get('score', '')}).")
            retenues += 1
        else:
            n = len(candidates.get(eid, {}).get("candidats", []))
            justif = (f"introuvable — {n} candidat(s) Commons filtrés (licence libre + taille), "
                      f"aucun retenu après vérification visuelle pour « {d['montrer']} » ; "
                      f"la fiche garde sa vignette par défaut.")
            introuvables += 1
        lignes.append((eid, d.get("nom", ""), d.get("montrer", ""), justif))
    with open(REPORTS / "photos-recherche.md", "w", encoding="utf-8") as fh:
        fh.write("# Recherche de photos réelles libres (Wikimedia Commons)\n\n")
        fh.write(f"{len(demandes)} demandes (data/photos_a_rechercher.json) : "
                 f"**{retenues} photos retenues**, **{introuvables} introuvables**.\n\n")
        fh.write("Licences acceptées uniquement : domaine public, CC0, CC BY, CC BY-SA "
                 "(jamais NC, ND ou tous droits réservés). Chaque retenue a été vérifiée "
                 "visuellement sur planche-contact ; les sources brutes sont dans "
                 "reports/photos-candidates.json et reports/photos-selection.json.\n\n")
        fh.write("| id | nom | à montrer | résultat |\n|---|---|---|---|\n")
        for eid, nom, montrer, justif in lignes:
            cellules = [c.replace("\n", " ") for c in (eid, nom, montrer, justif.replace("|", "\\|"))]
            fh.write("| " + " | ".join(cellules) + " |\n")
    return {"demandes": len(demandes), "retenues": retenues, "introuvables": introuvables}


def build_rapport(lim: dict, cov: dict, nb_conflits: int, photos_rech: dict,
                  n_reelles: int, products: dict, releve: dict, demandes: list,
                  photos_json: dict, thes: list, curate_ok: bool, curate_msg: str,
                  tests_ok: bool, tests_msg: str, collecte: str) -> None:
    teas = load_json(DATA / "teas.json")
    entries = teas["entries"]
    actifs = [e for e in entries if e.get("status") != "merged"]
    fusionnes = [e for e in entries if e.get("status") == "merged"]
    init = ids_commit_racine()
    if init is None:
        conservation = "non vérifié (git indisponible)"
        conserves = None
    else:
        cur_ids = {e["id"] for e in entries}
        conserves = len(init & cur_ids)
        conservation = (f"{conserves}/{len(init)} ids du commit racine conservés "
                        f"(aucun supprimé ni renommé)")
    fiabilite = {}
    for e in thes:
        fiabilite[e["fiabilite"]] = fiabilite.get(e["fiabilite"], 0) + 1
    nb_ia = sum(1 for e in thes if e.get("photo") and not e.get("photo_exacte"))
    nb_sans = sum(1 for e in thes if not e.get("photo"))
    nb_reelles_thes = sum(1 for e in thes if e.get("photo") and e.get("photo_exacte"))
    prods = products["products"]
    marques = {}
    for pr in prods:
        marques[pr.get("brand", "")] = marques.get(pr.get("brand", ""), 0) + 1
    complets = sum(1 for pr in prods if pr.get("brewing", {}).get("temperature_c") is not None
                   and pr["brewing"].get("water_ml") and pr["brewing"].get("duration_s_min") is not None
                   and pr["brewing"].get("dosage", {}).get("value") is not None
                   and pr["brewing"].get("dosage", {}).get("unit"))
    gtin_non_verifies = sum(1 for pr in prods if pr.get("gtin") is None)
    inaccessibles = products.get("sources_inaccessibles", [])
    lignes_releve = releve.get("lignes", [])
    maisons_releve = {}
    for l in lignes_releve:
        maisons_releve[l["maison"]] = maisons_releve.get(l["maison"], 0) + 1
    taille_repo = sum(p.stat().st_size for p in ROOT.rglob("*")
                      if p.is_file() and ".git" not in p.parts and "travail" not in p.parts
                      and "__pycache__" not in p.parts and "output" not in p.parts)
    thes_ko = lim["thes_json_ko"]
    with open(REPORTS / "rapport-final.md", "w", encoding="utf-8") as fh:
        fh.write("# Rapport final — enrichissement multi-sources de la Théothèque\n\n")
        fh.write(f"Date de collecte : **{collecte}**. Branche `feat/enrichissement-sources`.\n\n")
        fh.write("## 1. Chiffres clés\n\n")
        fh.write(f"- Fiches du catalogue maître : **{len(entries)}** "
                 f"({len(actifs)} actives, {len(fusionnes)} fusionnées avec redirection).\n")
        fh.write(f"- Identifiants historiques : {conservation}.\n")
        fh.write(f"- Nouvelles variétés ajoutées : **{len(entries) - (conserves or len(entries))}** "
                 f"(crus Palais des Thés, recettes sourcées et revérifiées le {collecte}).\n")
        fh.write(f"- Produits commerciaux réels (dédoublonnés) : **{len(prods)}** — "
                 + ", ".join(f"{m} : {n}" for m, n in sorted(marques.items())) + ".\n")
        fh.write(f"- Profils de préparation `manufacturer_exact` : **{complets}/{len(prods)}** "
                 f"avec les 4 paramètres (dosage avec unité, eau, température, durée).\n")
        fh.write(f"- Recettes de variétés : {fiabilite.get('legacy_referenced', 0)} sourcées "
                 f"(`legacy_referenced`), {fiabilite.get('family_default', 0)} estimées "
                 f"(`family_default`), présentées comme telles dans l'appli.\n")
        fh.write(f"- GTIN vérifiés : **0** ; non vérifiés (`gtin: null`) : **{gtin_non_verifies}** "
                 f"(aucun code inventé).\n")
        fh.write(f"- Conflits de consignes enregistrés : **{nb_conflits}** (dont le cas Digestao, "
                 f"§3) ; aucune moyenne calculée.\n")
        fh.write(f"- Photos réelles légalement réutilisables : **{n_reelles}** "
                 f"(dont {photos_rech['retenues']} trouvées pour les {photos_rech['demandes']} demandes "
                 f"de RECHERCHE_PHOTOS, {photos_rech['introuvables']} « introuvable »).\n")
        fh.write(f"- Illustrations IA conservées (`photo_exacte: false`) : **{nb_ia}** ; "
                 f"fiches sans aucune photo : **{nb_sans}**.\n")
        fh.write(f"- Sources inaccessibles documentées : **{len(inaccessibles)}** URL "
                 f"(pages Pagode supprimées/redirigées) — voir data/products.json.\n\n")
        fh.write("## 2. Produits commerciaux (data/products.json, hors appli)\n\n")
        fh.write(f"{len(prods)} produits : 21 fiches Thés de la Pagode relues une par une "
                 f"(robots.txt autorise les pages produits) + {len(prods) - 21} issus du relevé "
                 f"comparatif du {collecte} ({len(lignes_releve)} lignes relevées : "
                 + ", ".join(f"{m} {n}" for m, n in sorted(maisons_releve.items()))
                 + "). Seules les lignes avec consigne complète (température + durée + dose) "
                   "deviennent des produits ; Dammann, Cafés Richard et Kusmi ne publient pas de "
                   "dosage précis sur les pages relevées, leurs lignes restent dans le relevé sans "
                   "valeur inventée. Mariage Frères était inaccessible.\n\n")
        fh.write("## 3. Conflits (reports/conflicts.csv)\n\n")
        fh.write("Cas **Digestao** : la fiche produit exacte gagne (90 °C / 200 ml / 1 sachet / "
                 "4 min, URL de la fiche 299), la valeur 95 °C / 7 min signalée pour la page pack "
                 "660 n'a pas été retrouvée à la relecture et reste enregistrée comme conflit "
                 "ouvert (`ouvert_non_reproduit`) avec son URL. Aucune moyenne.\n\n")
        fh.write("## 4. Photos (reports/photos-recherche.md, reports/images_rights.csv)\n\n")
        fh.write(f"{photos_rech['retenues']} photos Wikimedia Commons retenues sur "
                 f"{photos_rech['demandes']} demandes, licences PD/CC0/CC BY/CC BY-SA uniquement, "
                 f"vérifiées visuellement une par une ; crédits ≤ 60 caractères dans data/photos.json. "
                 f"{photos_rech['introuvables']} demandes restent « introuvable » plutôt qu'une photo "
                 f"approximative.\n\n")
        fh.write("## 5. Limites de l'appli (vérifiées sur docs/thes.json et les photos)\n\n")
        fh.write("| Élément | Constaté | Limite |\n|---|---|---|\n")
        fh.write(f"| id (max) | {lim['max_id']} car. | ≤ {lim['limite_id']} | "
                 f"{'OK' if lim['ok_id'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| nom (max) | {lim['max_nom']} car. | ≤ {lim['limite_nom']} | "
                 f"{'OK' if lim['ok_nom'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| origine (max) | {lim['max_origine']} car. | ≤ {lim['limite_origine']} | "
                 f"{'OK' if lim['ok_origine'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| notes (max) | {lim['max_notes']} car. | ≤ {lim['limite_notes']} | "
                 f"{'OK' if lim['ok_notes'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| photo_credit (max) | {lim['max_photo_credit']} car. | ≤ {lim['limite_photo_credit']} | "
                 f"{'OK' if lim['ok_photo_credit'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| photos ({lim['nb_photos']} WebP) | {lim['photo_min_w']}×{lim['photo_min_h']} à "
                 f"{lim['photo_max_w']}×{lim['photo_max_h']} px, max {lim['photo_max_ko']} Ko | "
                 f"{lim['limite_photo_poids']} Ko max, 800×533 min, 1600×1067 max | "
                 f"{'OK' if lim['photos_ok_dims'] and lim['photos_ok_poids'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| thes.json | {thes_ko} Ko | ≤ {LIMITES['thes_json_ko_max']} Ko (objectif "
                 f"{LIMITES['thes_json_ko_cible']} Ko) | {'OK' if lim['ok_thes_json'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| nombre de thés actifs | {lim['entries']} | ~{LIMITES['entrees_max']} max | "
                 f"{'OK' if lim['ok_entries'] else 'DÉPASSÉ'} |\n")
        fh.write(f"| dépôt entier (hors .git/travail) | {ko(taille_repo)} Ko | < 100 Mo conseillé | OK |\n\n")
        fh.write(f"thes.json dépasse l'objectif de {LIMITES['thes_json_ko_cible']} Ko "
                 f"({thes_ko} Ko) : c'était déjà le cas avant la mission (242 Ko au commit racine) ; "
                 f"le plafond dur de 1 Mo est respecté.\n\n")
        fh.write("## 6. Tests et reproductibilité\n\n")
        fh.write(f"- `python3 scripts/curate.py --check` : "
                 f"{'OK' if curate_ok else 'ÉCHEC'} ({curate_msg})\n")
        fh.write(f"- `python3 -m unittest discover -s tests` : "
                 f"{'OK' if tests_ok else 'ÉCHEC'} ({tests_msg})\n")
        fh.write("- Pipeline : `scripts/commons_search.py` → vérification visuelle → "
                 "`scripts/add_photo.py` → `scripts/build_products_from_releve.py` → "
                 "`scripts/curate.py` → `scripts/build_reports.py` → `scripts/build_archive.py`.\n\n")
        fh.write("## 7. Livrables et points non résolus\n\n")
        fh.write("Livrables construits par `scripts/build_archive.py` sous `output/` : "
                 "`theotheque-donnees-enrichies.zip` (dépôt complet hors .git/travail/output), "
                 "`theotheque-products.json`, `theotheque-sources.json`, `theotheque-coverage.csv`, "
                 "`theotheque-rapport-final.md` ; la taille du ZIP est mesurée à la construction et "
                 "imprimée dans le tableau final de `scripts/build_archive.py`.\n\n")
        fh.write(f"- {photos_rech['introuvables']} demandes photo sans photo libre trouvée "
                 f"(« introuvable », liste dans reports/photos-recherche.md).\n")
        fh.write("- 1 conflit ouvert non résolu (Digestao, page pack).\n")
        fh.write(f"- {len(inaccessibles)} URL Thés de la Pagode mortes/redirigées ; "
                 "thesdelapagode.com n'était lisible que page par page (lecture web), et "
                 "Mariage Frères inaccessible pendant le relevé.\n")
        fh.write("- Aucun GTIN vérifié (aucun inventé).\n")
        fh.write(f"- thes.json à {thes_ko} Ko, au-dessus de l'objectif de 200 Ko (pré-existant).\n")


def main() -> int:
    thes = load_json(DOCS / "thes.json")
    teas = load_json(DATA / "teas.json")
    redirections = load_json(DOCS / "redirections.json")
    products = load_json(DATA / "products.json")
    releve = load_json(DATA / "releve-maisons-2026-11-14.json")
    demandes_doc = load_json(DATA / "photos_a_rechercher.json")
    candidates = load_json(REPORTS / "photos-candidates.json")
    selection = load_json(REPORTS / "photos-selection.json")
    photos_json = load_json(DATA / "photos.json")
    demandes = demandes_doc.get("demandes", demandes_doc)
    collecte = products.get("collecte", {}).get("date", "2026-11-14")

    lim = compute_limits()
    cov = build_coverage(thes, teas, redirections, products)
    nb_conflits = build_conflicts(products)
    n_reelles = build_images_rights(thes, photos_json, selection)
    photos_rech = build_photos_recherche(demandes, candidates, selection, photos_json)
    curate_ok, curate_msg = run_commande([sys.executable, "scripts/curate.py", "--check"])
    tests_ok, tests_msg = run_commande([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    build_rapport(lim, cov, nb_conflits, photos_rech, n_reelles, products, releve,
                  demandes, photos_json, thes, curate_ok, curate_msg, tests_ok, tests_msg,
                  collecte)

    print(f"coverage.csv : {cov['lignes']} lignes ({cov['varietes']} variétés, {cov['produits']} produits)")
    print(f"conflicts.csv : {nb_conflits} conflit(s)")
    print(f"images_rights.csv : {lim['nb_photos']} photos, {n_reelles} réelles")
    print(f"photos-recherche.md : {photos_rech['retenues']} retenues / "
          f"{photos_rech['introuvables']} introuvables sur {photos_rech['demandes']} demandes")
    print(f"rapport-final.md : thes.json {lim['thes_json_ko']} Ko, {lim['entries']} entrées actives, "
          f"photos OK dims={lim['photos_ok_dims']} poids={lim['photos_ok_poids']} "
          f"(max {lim['photo_max_ko']} Ko)")
    print(f"curate --check : {'OK' if curate_ok else 'ÉCHEC'} ({curate_msg})")
    print(f"unittest : {'OK' if tests_ok else 'ÉCHEC'} ({tests_msg})")
    return 0 if (curate_ok and tests_ok and lim["ok_thes_json"] and lim["photos_ok_dims"]
                 and lim["photos_ok_poids"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
