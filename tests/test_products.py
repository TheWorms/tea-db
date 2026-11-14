"""Tests des fiches produits commerciaux (data/products.json).

V\u00e9rifie que le fichier s\u00e9par\u00e9 des vari\u00e9t\u00e9s reste coh\u00e9rent : ids stables et
courts, consignes fabricant sourc\u00e9es et dat\u00e9es, jamais de conversion fictive
sachet/cuill\u00e8re \u2192 grammes, cas Digestao exact avec son conflit enregistr\u00e9,
pas de moyenne sur des consignes contradictoires, aucun GTIN invent\u00e9, et
s\u00e9paration d'avec docs/thes.json (les produits n'y entrent pas).

    python3 -m unittest discover -s tests
"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ProductsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "data" / "products.json").read_text(encoding="utf-8"))
        cls.products = cls.doc["products"]
        cls.by_id = {p["id"]: p for p in cls.products}
        cls.app = json.loads((ROOT / "docs" / "thes.json").read_text(encoding="utf-8"))
        cls.app_ids = {t["id"] for t in cls.app}
        cls.catalog = json.loads((ROOT / "data" / "teas.json").read_text(encoding="utf-8"))
        cls.catalog_ids = {e["id"] for e in cls.catalog["entries"]}

    def test_ids_uniques_et_courts(self):
        ids = [p["id"] for p in self.products]
        self.assertEqual(len(ids), len(set(ids)))
        for p in self.products:
            self.assertLessEqual(len(p["id"]), 40, p["id"])

    def test_produits_separes_des_varietes(self):
        # un produit commercial ne doit ni entrer dans docs/thes.json ni remplacer une fiche
        for p in self.products:
            self.assertNotIn(p["id"], self.app_ids, p["id"])
        for p in self.products:
            if p["variety_id"] is not None:
                self.assertIn(p["variety_id"], self.catalog_ids, p["id"])

    def test_manufacturer_exact_a_url_officielle_et_date(self):
        maisons = ("thesdelapagode.com", "palaisdesthes.com", "dammann.fr",
                   "cafesrichard.fr", "kusmitea.com")
        for p in self.products:
            b = p["brewing"]
            self.assertEqual(b["confidence"], "manufacturer_exact", p["id"])
            self.assertTrue(b["source_url"].startswith("https://"), p["id"])
            self.assertTrue(any(m in b["source_url"] for m in maisons),
                            f"{p['id']} : {b['source_url']}")
            self.assertRegex(b["collected_on"], r"^\d{4}-\d{2}-\d{2}$", p["id"])
            self.assertTrue(p["brand"] and p["name"], p["id"])

    def test_quatre_parametres_presents(self):
        for p in self.products:
            b = p["brewing"]
            for key in ("temperature_c", "water_ml", "duration_s_min", "duration_s_max"):
                self.assertIsNotNone(b[key], f"{p['id']}.{key}")
            self.assertIsNotNone(b["dosage"]["value"], p["id"])
            self.assertIn(b["dosage"]["unit"], ("grams", "sachet", "cuill\u00e8re \u00e0 caf\u00e9"), p["id"])
            self.assertLessEqual(b["duration_s_min"], b["duration_s_max"], p["id"])

    def test_sachet_ou_cuillere_jamais_convertis_en_grammes(self):
        for p in self.products:
            b = p["brewing"]
            if b["dosage"]["unit"] == "grams":
                self.assertEqual(b["dose_g"], b["dosage"]["value"], p["id"])
            else:
                self.assertIsNone(b["dose_g"], f"{p['id']} : {b['dosage']['unit']} converti en grammes")

    def test_digestao_exact_et_conflit_enregistre(self):
        d = self.by_id["pagode-digestao-18s"]
        b = d["brewing"]
        self.assertEqual((b["temperature_c"], b["water_ml"], b["dosage"]["value"], b["dosage"]["unit"],
                          b["duration_s_min"], b["duration_s_max"]), (90, 200, 1, "sachet", 240, 240))
        self.assertTrue(d["conflict_detected"])
        conflits = [c for c in self.doc["conflicts"] if c["product_id"] == "pagode-digestao-18s"]
        self.assertEqual(len(conflits), 1)
        c = conflits[0]
        self.assertEqual(c["chosen"]["temperature_c"], 90)
        self.assertEqual(c["chosen"]["duration_s"], 240)
        self.assertEqual(c["rejected"]["temperature_c"], 95)
        self.assertEqual(c["rejected"]["duration_s"], 420)
        self.assertIn("660-pack-digestion", c["rejected"]["url"])

    def test_aucune_moyenne_sur_conflit(self):
        for c in self.doc["conflicts"]:
            p = self.by_id[c["product_id"]]
            b = p["brewing"]
            valeurs = {c["chosen"]["temperature_c"], c["rejected"]["temperature_c"]}
            if len(valeurs) > 1:
                moyenne = sum(valeurs) / 2
                self.assertNotEqual(b["temperature_c"], moyenne, p["id"])
            self.assertEqual(b["temperature_c"], c["chosen"]["temperature_c"], p["id"])
            self.assertEqual(b["duration_s_min"], c["chosen"]["duration_s"], p["id"])

    def test_aucun_gtin_invente(self):
        for p in self.products:
            self.assertIsNone(p["gtin"], p["id"])
            self.assertEqual(p["gtin_status"], "non_verifie", p["id"])

    def test_photos_commerciales_non_reutilisees(self):
        for p in self.products:
            self.assertIsNone(p["photo"], p["id"])
            self.assertEqual(p["photo_status"], "rights_pending", p["id"])

    def test_sources_inaccessibles_documentees(self):
        for s in self.doc["sources_inaccessibles"]:
            self.assertTrue(s["url"].startswith("https://"))
            self.assertIn(s["statut"], ("page_supprimee", "redirection_categorie", "inaccessible"))

    def test_ingredients_sont_une_liste_de_chaines(self):
        # le relev\u00e9 comparatif ne publie pas toujours la composition compl\u00e8te : liste vide autoris\u00e9e, jamais invent\u00e9e
        for p in self.products:
            self.assertIsInstance(p["ingredients"], list, p["id"])
            for ing in p["ingredients"]:
                self.assertIsInstance(ing, str, p["id"])


if __name__ == "__main__":
    unittest.main()
