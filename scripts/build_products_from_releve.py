#!/usr/bin/env python3
"""Transforme le relev\u00e9 comparatif des grandes maisons (data/releve-maisons-2026-11-14.json)
en fiches produits de data/products.json.

    python3 scripts/build_products_from_releve.py

Seules les lignes avec une consigne publi\u00e9e compl\u00e8te (temp\u00e9rature + dur\u00e9e + dose)
deviennent des produits ; les autres (Dammann, Caf\u00e9s Richard, Kusmi sans param\u00e8tres)
restent document\u00e9es dans le relev\u00e9, sans valeur invent\u00e9e. Id d\u00e9terministe d\u00e9riv\u00e9 de
l'URL (maison + n\u00b0 de fiche), 40 caract\u00e8res max. cl -> ml, min -> s, "3 min45" -> 225 s.
Une dose en sachets/cuill\u00e8res n'est jamais convertie en grammes. Aucun GTIN invent\u00e9.
Les produits d\u00e9j\u00e0 pr\u00e9sents dans data/products.json (collecte Pagode du 14/11) sont conserv\u00e9s.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEVE = ROOT / "data" / "releve-maisons-2026-11-14.json"
PRODUCTS = ROOT / "data" / "products.json"

MAISON_PREFIX = {
    "Palais des Th\u00e9s": "palais",
    "Dammann Fr\u00e8res": "dammann",
    "Caf\u00e9s Richard": "cafesrichard",
    "Kusmi Tea": "kusmi",
    "Th\u00e9s de la Pagode": "pagode",
}
SECTION_CATEGORY = [
    (re.compile(r"noirs?|black", re.I), "black_tea"),
    (re.compile(r"verts?|green|sencha", re.I), "green_tea"),
    (re.compile(r"blancs?|white", re.I), "white_tea"),
    (re.compile(r"oolong|wulong", re.I), "oolong"),
    (re.compile(r"jaune|yellow", re.I), "yellow_tea"),
    (re.compile(r"pu ?erh|sombre|dark", re.I), "pu_erh"),
    (re.compile(r"matcha", re.I), "matcha"),
    (re.compile(r"rooibos", re.I), "rooibos"),
    (re.compile(r"mat\u00e9|mate", re.I), "mate"),
    (re.compile(r"tisane|infusion|herboriste", re.I), "herbal_infusion"),
    (re.compile(r"glac|iced", re.I), "iced_tea"),
    (re.compile(r"earl grey|bergamote", re.I), "earl_grey"),
]


def parse_temp(s: str):
    m = re.search(r"(\d+)\s*\u00b0?\s*C", s or "")
    return int(m.group(1)) if m else None


def parse_duree(s: str):
    """'4 min' -> (240,240) ; '3 min45' -> (225,225) ; '8 min - 10 min' -> (480,600) ; '15\"' -> (15,15)."""
    s = (s or "").strip()
    m = re.match(r'^(\d+)\s*min(?:\s*(\d+)\s*(?:s|sec))?', s)
    if m:
        d = int(m.group(1)) * 60 + int(m.group(2) or 0)
        return d, d
    m = re.match(r'^(\d+)\s*min\s*-\s*(\d+)\s*min(?:\s*(\d+)\s*s)?$', s)
    if m:
        return int(m.group(1)) * 60, int(m.group(2)) * 60 + int(m.group(3) or 0)
    m = re.match(r'^(\d+)\s*"', s)
    if m:
        return int(m.group(1)), int(m.group(1))
    return None, None


def parse_dose_water(s: str):
    """'6g / 30cl' -> ({'value':6,'unit':'grams'}, 300) ; '1 cuill\u00e8re \u00e0 caf\u00e9 rase / 5 cl' -> (cuill\u00e8re, 50)."""
    s = (s or "").strip()
    m = re.match(r'^([\d,\.]+)\s*g\s*/\s*([\d,\.]+)\s*(cl|ml|L)', s, re.I)
    if m:
        g = float(m.group(1).replace(",", "."))
        vol, unit = float(m.group(2).replace(",", ".")), m.group(3).lower()
        ml = vol * 1000 if unit == "l" else vol * 10 if unit == "cl" else vol
        return {"value": g, "unit": "grams"}, ml
    m = re.match(r'^([\d,\.]+)\s*(sachet|sachets|cuill\u00e8re(?:s)?(?: \u00e0 caf\u00e9)?(?: rase)?)\s*/\s*([\d,\.]+)\s*(cl|ml|L)?', s, re.I)
    if m:
        val = float(m.group(1).replace(",", "."))
        unit = "sachet" if "sachet" in m.group(2).lower() else "cuill\u00e8re \u00e0 caf\u00e9"
        vol = m.group(3)
        u = (m.group(4) or "").lower()
        ml = None
        if vol:
            v = float(vol.replace(",", "."))
            ml = v * 1000 if u == "l" else v * 10 if u == "cl" else v
        return {"value": val, "unit": unit}, ml
    return None, None


def slug_id(maison: str, url: str, nom: str) -> str:
    prefix = MAISON_PREFIX.get(maison, "maison")
    m = re.search(r"-(\d+)\.html", url or "")
    if m:
        pid = f"{prefix}-{m.group(1)}"
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", nom.lower().strip(" ."))[:24].strip("-")
        pid = f"{prefix}-{slug}"
    return pid[:40]


def main() -> int:
    releve = json.load(open(RELEVE, encoding="utf-8"))
    doc = json.load(open(PRODUCTS, encoding="utf-8"))
    existing_urls = {p["brewing"]["source_url"] for p in doc["products"]}
    existing_ids = {p["id"] for p in doc["products"]}

    added = 0
    for r in releve["lignes"]:
        url = r.get("url", "")
        if not url or url in existing_urls:
            continue
        temp = parse_temp(r.get("temp", ""))
        dmin, dmax = parse_duree(r.get("duree", ""))
        dose, water = parse_dose_water(r.get("dose", ""))
        if temp is None or dmin is None or dose is None:
            continue  # pas de consigne publi\u00e9e : on n'invente rien
        pid = slug_id(r["maison"], url, r["nom"])
        if pid in existing_ids:
            continue
        cat = "other"
        for rx, c in SECTION_CATEGORY:
            if rx.search(r.get("section") or "") or rx.search(r["nom"]):
                cat = c
                break
        method = "whisk" if dose["unit"].startswith("cuill\u00e8re") else "western"
        brewing = {
            "method": method,
            "raw": {"temperature": r.get("temp", ""), "dosage": r.get("dose", ""),
                    "duration": r.get("duree", ""), "moment": r.get("moment", "")},
            "temperature_c": temp,
            "water_ml": water,
            "duration_s_min": dmin,
            "duration_s_max": dmax,
            "dosage": dose,
            "dose_g": dose["value"] if dose["unit"] == "grams" else None,
            "confidence": "manufacturer_exact",
            "source_url": url,
            "collected_on": releve["date_releve"],
            "releve": "data/releve-maisons-2026-11-14.json",
        }
        if water and water > 350:
            brewing["water_scaling"] = "linear_dose_only"
            brewing["water_scaling_note"] = f"{water} ml d\u00e9passe les 350 ml de l'appli : ramen\u00e9 \u00e0 350 ml avec la dose r\u00e9duite en proportion."
        doc["products"].append({
            "id": pid,
            "brand": r["maison"],
            "name": r["nom"],
            "category": cat,
            "type": r.get("section", ""),
            "packaging": None,
            "gtin": None,
            "gtin_status": "non_verifie",
            "variety_id": None,
            "ingredients": [],
            "brewing": brewing,
            "conflict_detected": False,
            "photo": None,
            "photo_status": "rights_pending",
        })
        existing_ids.add(pid)
        existing_urls.add(url)
        added += 1

    doc["products"].sort(key=lambda p: p["id"])
    doc.setdefault("_doc_fr", "")
    PRODUCTS.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{added} produits ajout\u00e9s depuis le relev\u00e9 ; total {len(doc['products'])} produits.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
