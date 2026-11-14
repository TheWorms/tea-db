"""Tests des rapports et des limites de l'appli (reports/, output/, photos).

Vérifie que les rapports générés couvrent bien toutes les variétés, tous les
produits et toutes les demandes photo ; que les conflits ne moyennent rien ;
et que docs/thes.json et les photos respectent les limites lues par l'appli
(id 40, nom 30, origine 30, notes 300, crédit 60, thes.json 1 Mo, ~2000 thés,
photos 800×533 à 1600×1067 et 200 Ko max).

    python3 -m unittest discover -s tests
"""
import csv
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


curate = load_script("curate")


class RapportsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.thes = load_json(ROOT / "docs" / "thes.json")
        cls.teas = load_json(ROOT / "data" / "teas.json")
        cls.products = load_json(ROOT / "data" / "products.json")
        cls.demandes = load_json(ROOT / "data" / "photos_a_rechercher.json")["demandes"]
        cls.photos_json = load_json(ROOT / "data" / "photos.json")
        cls.reports = ROOT / "reports"

    def test_rapports_existent(self):
        for nom in ("coverage.csv", "conflicts.csv", "images_rights.csv",
                    "photos-recherche.md", "rapport-final.md"):
            self.assertTrue((self.reports / nom).is_file(), nom)

    def test_coverage_une_ligne_par_entree_et_par_produit(self):
        with open(self.reports / "coverage.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        varietes = [r for r in rows if r["type"] == "variete"]
        produits = [r for r in rows if r["type"] == "produit"]
        self.assertEqual(len(varietes), len(self.teas["entries"]))
        self.assertEqual(len(produits), len(self.products["products"]))
        self.assertEqual({r["id"] for r in produits}, {p["id"] for p in self.products["products"]})

    def test_photos_recherche_couvre_toutes_les_demandes(self):
        texte = (self.reports / "photos-recherche.md").read_text(encoding="utf-8")
        for d in self.demandes:
            self.assertIn(d["id"], texte)
        retenues = [d["id"] for d in self.demandes
                    if (self.reports.parent / "docs" / "assets" / "photos" / "catalogue"
                        / f"{d['id']}.webp").exists()
                    and self.photos_json["photos"].get(d["id"], {}).get("exacte")]
        self.assertIn(f"**{len(retenues)} photos retenues**", texte)
        self.assertIn("introuvable", texte)

    def test_conflicts_sans_moyenne_digestao(self):
        with open(self.reports / "conflicts.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        self.assertTrue(any(r["produit_id"] == "pagode-digestao-18s" for r in rows))
        ligne = next(r for r in rows if r["produit_id"] == "pagode-digestao-18s")
        retenu = json.loads(ligne["retenu"])
        rejete = json.loads(ligne["rejete"])
        self.assertEqual((retenu["temperature_c"], retenu["water_ml"], retenu["duration_s"]),
                         (90, 200, 240))
        self.assertEqual((rejete["temperature_c"], rejete["duration_s"]), (95, 420))
        self.assertNotIn("92", ligne["retenu"])

    def test_images_rights_une_ligne_par_photo(self):
        with open(self.reports / "images_rights.csv", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        webp = list((ROOT / "docs" / "assets" / "photos" / "catalogue").glob("*.webp"))
        self.assertEqual(len(rows), len(webp))
        reelles = [r for r in rows if r["photo_exacte"] == "oui"]
        for r in reelles:
            licence = (r["licence"] + " " + r["credit"]).lower()
            self.assertRegex(licence, r"cc0|cc by|public domain", r["id"])
            self.assertNotRegex(r["licence"].lower(),
                                r"by-nc|by-nd|allrights|noncommercial|no-deriv", r["id"])
            self.assertTrue(r["page_source"].startswith("https://commons.wikimedia.org/"), r["id"])
            self.assertLessEqual(len(r["credit"]), 60)


class LimitesAppliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.thes = load_json(ROOT / "docs" / "thes.json")
        cls.photo_dir = ROOT / "docs" / "assets" / "photos" / "catalogue"

    def test_champs_thes_json_dans_les_limites(self):
        limites = {"id": 40, "nom": 30, "origine": 30, "notes": 300, "photo_credit": 60}
        for e in self.thes:
            for champ, maxlen in limites.items():
                valeur = e.get(champ) or ""
                self.assertLessEqual(len(valeur), maxlen, f"{e['id']} champ {champ}")

    def test_thes_json_taille_et_nombre(self):
        taille = (ROOT / "docs" / "thes.json").stat().st_size
        self.assertLessEqual(taille, 1024 * 1024)
        self.assertLessEqual(len(self.thes), 2000)

    def test_photos_dimensions_et_poids(self):
        for path in self.photo_dir.glob("*.webp"):
            w, h = curate.webp_size(path)
            self.assertGreaterEqual((w, h), (800, 533), path.name)
            self.assertLessEqual((w, h), (1600, 1067), path.name)
            self.assertLessEqual(path.stat().st_size, 200 * 1024, path.name)

    def test_references_photos_coherentes(self):
        ids = {e["id"] for e in self.thes}
        for e in self.thes:
            if e.get("photo"):
                self.assertTrue((ROOT / "docs" / e["photo"]).exists(), e["id"])
        for path in self.photo_dir.glob("*.webp"):
            self.assertIn(path.stem, ids, path.name)


class LivrablesTests(unittest.TestCase):
    def test_output_present(self):
        output = ROOT / "output"
        if not output.is_dir():
            self.skipTest("output/ pas encore construit (scripts/build_archive.py)")
        for nom in ("theotheque-donnees-enrichies.zip", "theotheque-products.json",
                    "theotheque-sources.json", "theotheque-coverage.csv",
                    "theotheque-rapport-final.md"):
            self.assertTrue((output / nom).is_file(), nom)
        self.assertLess((output / "theotheque-donnees-enrichies.zip").stat().st_size,
                        100 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
