"""Tests de curation, du fichier de l'appli et du script photo.

Bibliothèque standard uniquement ; les tests d'images utilisent Pillow s'il est
installé et sont sautés sinon.

    python3 -m unittest discover -s tests
"""
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


curate_mod = load_script("curate")
photo_mod = load_script("add_photo")

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

APP_KEYS = ["id", "nom", "famille", "origine", "eau_ml", "the_g", "temperature_c", "duree_s",
            "duree_max_s", "fiabilite", "photo", "photo_credit", "photo_exacte", "notes", "source", "theine"]


def fake_photos(*ids):
    return {i: {"width": 1200, "height": 800, "bytes": 90_000} for i in ids}


class CurateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((ROOT / "data" / "teas.json").read_text(encoding="utf-8"))
        cls.cur = curate_mod.load_curation(ROOT)
        cls.photos = curate_mod.scan_photos(curate_mod.PHOTO_DIR)
        cls.by_id = {e["id"]: e for e in cls.catalog["entries"]}
        cls.app_text = (ROOT / "docs" / "thes.json").read_text(encoding="utf-8")
        cls.app = json.loads(cls.app_text)
        cls.app_by_id = {t["id"]: t for t in cls.app}
        cls.redirections = json.loads((ROOT / "docs" / "redirections.json").read_text(encoding="utf-8"))
        cls.test_id = next(e["id"] for e in cls.catalog["entries"] if e["status"] == "active")
        cls.photos_without = {k: v for k, v in cls.photos.items() if k != cls.test_id}

    def curate(self, cur=None, photos=None, catalog=None):
        return curate_mod.curate(catalog or self.catalog, cur or self.cur,
                                 self.photos if photos is None else photos)

    def app_tea(self, catalog, tea_id):
        return next(t for t in json.loads(curate_mod.render_app(catalog)) if t["id"] == tea_id)

    # --- fichiers publiés ------------------------------------------------- #
    def test_published_files_are_up_to_date(self):
        outputs, _, _ = curate_mod.render_all(ROOT)
        for path, text in outputs.items():
            with open(path, encoding="utf-8", newline="") as fh:
                self.assertEqual(fh.read(), text, f"{path.name} pas à jour : lancer scripts/curate.py")

    def test_idempotent(self):
        once = self.curate()
        self.assertEqual(once, curate_mod.curate(once, self.cur, self.photos))

    def test_reset_restores_original_shape(self):
        for e in curate_mod.reset(self.catalog)["entries"]:
            self.assertNotIn("status", e)
            self.assertNotIn("notes_fr", e)
            self.assertIsNone(e["image"])
            self.assertIn(e["recipes"][0]["reliability"], ("legacy_referenced", "family_default"))

    # --- fichier de l'appli ----------------------------------------------- #
    def test_app_file_is_a_sorted_list_with_app_keys(self):
        self.assertIsInstance(self.app, list)
        self.assertEqual([t["id"] for t in self.app], sorted(t["id"] for t in self.app))
        for tea in self.app:
            self.assertEqual([k for k in tea if k in APP_KEYS], APP_KEYS, tea["id"])

    def test_app_file_limits(self):
        self.assertLessEqual(len(self.app_text.encode("utf-8")), curate_mod.APP_FILE_MAX_BYTES)
        for tea in self.app:
            self.assertLessEqual(len(tea["id"]), 40, tea["id"])
            self.assertLessEqual(len(tea["nom"]), 30, tea["id"])
            self.assertLessEqual(len(tea["origine"] or ""), 30, tea["id"])
            self.assertLessEqual(len(tea["notes"] or ""), 300, tea["id"])
            self.assertLessEqual(len(tea["photo_credit"] or ""), 60, tea["id"])
            self.assertLessEqual(tea["eau_ml"], curate_mod.MAX_EAU_ML, tea["id"])
            self.assertNotIn(tea["nom"].casefold(), [a.casefold() for a in tea.get("alias", [])])
            self.assertIn(tea["fiabilite"], ("legacy_referenced", "family_default"))
            self.assertIn(tea["theine"], ("oui", "non", "inconnu"))
            self.assertTrue(tea["source"].startswith("https://"), tea["id"])

    def test_reliability_sent_to_the_app(self):
        # l'appli ne connaît que deux valeurs : une recette de style est sourcée, une copie de thé voisin est estimée
        self.assertEqual(curate_mod.RELIABILITY_APP["style_referenced"], "legacy_referenced")
        self.assertEqual(curate_mod.RELIABILITY_APP["subfamily_default"], "family_default")
        for e in self.catalog["entries"]:
            if e["status"] == "active":
                expected = curate_mod.RELIABILITY_APP[e["recipes"][0]["reliability"]]
                self.assertEqual(self.app_by_id[e["id"]]["fiabilite"], expected, e["id"])

    def test_water_capped_at_350_ml_with_same_ratio(self):
        capped = 0
        for tea in self.app:
            src = self.by_id[tea["id"]]["recipes"][0]
            if src["water_ml"] > curate_mod.MAX_EAU_ML:
                capped += 1
                self.assertEqual(tea["eau_ml"], 350, tea["id"])
                self.assertAlmostEqual(tea["the_g"] / 350, src["tea_g"] / src["water_ml"], places=3)
                self.assertEqual(tea["duree_s"], src["duration_seconds_min"])
            else:
                self.assertEqual(tea["eau_ml"], src["water_ml"], tea["id"])
        self.assertGreater(capped, 0)

    def test_every_tea_has_notes(self):
        self.assertTrue(all(t["notes"] for t in self.app))

    def test_redirections_point_to_kept_teas(self):
        ids = set(self.app_by_id)
        for old, new in self.redirections.items():
            self.assertNotIn(old, ids)
            self.assertIn(new, ids)
        self.assertEqual(len(ids) + len(self.redirections), len(self.catalog["entries"]))

    def test_app_ids_of_iced_teas_kept(self):
        for i in ("cold-the-vert-glace-a-temperatu-99871427", "cold-tisane-glacee-a-temperatur-d9505d99"):
            self.assertIn(i, self.app_by_id)

    # --- photos ------------------------------------------------------------ #
    def test_photo_fields(self):
        for tea in self.app:
            if tea["photo"] is None:
                self.assertIsNone(tea["photo_credit"], tea["id"])
                self.assertFalse(tea["photo_exacte"], tea["id"])
            else:
                self.assertEqual(tea["photo"], f"assets/photos/catalogue/{tea['id']}.webp")
                self.assertTrue((ROOT / "docs" / tea["photo"]).is_file(), tea["id"])
                extra = self.cur["photos"]["photos"].get(tea["id"], {})
                self.assertEqual(tea["photo_credit"], extra.get("credit", self.cur["photos"]["credit_par_defaut"]))
                self.assertEqual(tea["photo_exacte"], bool(extra.get("exacte", False)))

    def test_new_photo_is_used_and_can_be_removed(self):
        tid = self.test_id
        out = self.curate(photos={**self.photos_without, **fake_photos(tid)})
        tea = self.app_tea(out, tid)
        self.assertEqual(tea["photo"], f"assets/photos/catalogue/{tid}.webp")
        self.assertEqual(tea["photo_credit"], "Théothèque (IA)")
        back = curate_mod.curate(out, self.cur, self.photos_without)
        self.assertIsNone(self.app_tea(back, tid)["photo"])

    def test_credit_exception(self):
        tid = self.test_id
        cur = copy.deepcopy(self.cur)
        cur["photos"]["photos"][tid] = {"credit": "Thib", "exacte": True}
        tea = self.app_tea(self.curate(cur, {**self.photos_without, **fake_photos(tid)}), tid)
        self.assertEqual((tea["photo_credit"], tea["photo_exacte"]), ("Thib", True))
        with self.assertRaises(curate_mod.CurationError):    # exception sans fichier
            self.curate(cur, self.photos_without)

    def test_rejects_photo_of_merged_or_unknown_tea(self):
        merged = next(iter(self.redirections))
        for bad in (merged, "green-inconnu"):
            with self.assertRaises(curate_mod.CurationError, msg=bad):
                self.curate(photos={**self.photos, **fake_photos(bad)})

    # --- textes et données ------------------------------------------------ #
    def test_rejects_too_long_texts(self):
        for field, value in (("notes", "x" * 301), ("origine", "x" * 31), ("nom", "x" * 31)):
            cur = copy.deepcopy(self.cur)
            cur["textes"]["green-sencha"] = {**cur["textes"]["green-sencha"], field: value}
            with self.assertRaises(curate_mod.CurationError, msg=field):
                self.curate(cur)

    def test_rejects_too_long_id(self):
        cat = copy.deepcopy(self.catalog)
        cat["entries"][0]["id"] = "x" * 41
        with self.assertRaises(curate_mod.CurationError):
            self.curate(catalog=cat)

    def test_ids_never_removed(self):
        ids = [e["id"] for e in self.catalog["entries"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), self.catalog["stats"]["entries"])

    def test_replaced_by_points_to_active_entry(self):
        for e in self.catalog["entries"]:
            if e["status"] == "merged":
                target = self.by_id[e["replaced_by"]]
                self.assertEqual(target["status"], "active", e["id"])
                self.assertIn(e["id"], target["merged_from"])
                names = {a.casefold() for a in target["aliases"]} | {target["name"].casefold()}
                self.assertIn(e["name"].casefold(), names)

    def test_subfamily_recipes_copy_a_sourced_anchor(self):
        for e in self.catalog["entries"]:
            r = e["recipes"][0]
            if r["reliability"] == "subfamily_default":
                a = self.by_id[r["derived_from"]]["recipes"][0]
                self.assertEqual(a["reliability"], "legacy_referenced")
                for k in ("tea_g", "water_ml", "temperature_c", "duration_seconds_min",
                          "duration_seconds_max", "method"):
                    self.assertEqual(r[k], a[k], f"{e['id']}.{k}")

    def test_known_contradictions_fixed(self):
        temp = lambda i: self.by_id[i]["recipes"][0]["temperature_c"]  # noqa: E731
        self.assertEqual(temp("green-uji-gyokuro"), temp("green-gyokuro"))
        self.assertEqual(self.by_id["black-darjeeling-second-flush"]["style"]["key"], "noir-darjeeling-ete")
        self.assertEqual(temp("pu_erh-shou-pu-erh-vieilli"), temp("pu_erh-shou-pu-erh"))
        self.assertEqual(self.by_id["green-nishio-matcha"]["recipes"][0]["method"], "whisk")
        self.assertEqual(self.by_id["green-the-vert-glace"]["recipes"][0]["method"], "room_temperature")

    def test_verified_values_still_match(self):
        for ver in self.cur["verifications"]:
            current = self.by_id[ver["id"]]["recipes"][0]
            r = current.get("legacy_recipe") or current      # recette d'origine, même alignée sur un style
            self.assertEqual(r["source"]["checked_on"], ver["checked_on"], ver["id"])
            for k, v in ver["expected"].items():
                self.assertEqual(float(r[k]), float(v), f"{ver['id']}.{k}")
            if "legacy_recipe" not in current:
                self.assertEqual(self.app_by_id[ver["id"]].get("source_verifiee"), ver["checked_on"])

    def test_theine(self):
        for i in ("herbal-mate-vert", "herbal-guayusa", "herbal-yaupon"):
            self.assertEqual(self.app_by_id[i]["theine"], "oui")
        none = sorted(e["id"] for e in self.catalog["entries"] if e["caffeine"]["status"] == "none")
        self.assertEqual(none, sorted(self.cur["cautions"]["caffeine"]["none"]))

    # --- styles sourcés ------------------------------------------------------ #
    def test_style_recipes_match_their_sources(self):
        for style in self.cur["styles"]:
            computed, problems = curate_mod.style_recipe(style)
            self.assertEqual(problems, [], style["key"])
            self.assertGreaterEqual(len({x["maison"] for x in style["sources"]}), 2, style["key"])
            for member_id in style["members"]:
                r = self.by_id[member_id]["recipes"][0]
                self.assertEqual(r["reliability"], "style_referenced", member_id)
                for k, v in computed.items():
                    self.assertEqual(r[k], v, f"{member_id}.{k}")
                tea = self.app_by_id[member_id]
                self.assertEqual(tea["fiabilite"], "legacy_referenced", member_id)
                self.assertEqual(tea["source"], style["sources"][0]["url"], member_id)

    def test_style_rounding_and_rules(self):
        src = lambda house, g, ml, t, d: {"maison": house, "the": "x", "url": "https://x", "dose_g": g,  # noqa: E731
                                          "eau_ml": ml, "temp_c": t, "duree_s": d}
        style = {"key": "essai", "sources": [src("A", 2.5, 200, [95, 95], [180, 300]),
                                             src("B", 11, 1000, [90, 100], [240, 300])]}
        recipe, problems = curate_mod.style_recipe(style)
        self.assertEqual(problems, [])
        # dose : médiane de 3,125 et 2,75 = 2,94 -> 3 ; température : 95 ; durées : 210 et 300
        self.assertEqual(recipe, {"water_ml": 250, "tea_g": 3.0, "temperature_c": 95,
                                  "duration_seconds_min": 210, "duration_seconds_max": 300})
        one_house = {"key": "essai", "sources": [src("A", 2.5, 200, [95, 95], [180, 300])] * 2}
        self.assertTrue(curate_mod.style_recipe(one_house)[1])
        # une maison = une voix : trois sources de A (90 °C) ne l'emportent pas sur B et C (100 °C)
        voix = {"key": "essai", "sources": [src("A", 3, 250, [90, 90], [180, 180])] * 3
                + [src("B", 3, 250, [100, 100], [180, 180]), src("C", 3, 250, [100, 100], [180, 180])]}
        self.assertEqual(curate_mod.style_recipe(voix)[0]["temperature_c"], 100)
        self.assertEqual(curate_mod._round(92.5, 5), 90)   # égalité : vers le bas

    def test_sourced_member_keeps_its_recipe_and_source(self):
        aligned = [e for e in self.catalog["entries"] if e["recipes"][0].get("legacy_recipe")]
        self.assertGreater(len(aligned), 0)
        for e in aligned:
            style = next(x for x in self.cur["styles"] if x["key"] == e["style"]["key"])
            self.assertIn(e["recipes"][0]["legacy_recipe"]["source"]["url"], {x["url"] for x in style["sources"]})
        back = curate_mod.reset(self.catalog)
        assam = next(x for x in back["entries"] if x["id"] == "black-assam")["recipes"][0]
        self.assertEqual((assam["tea_g"], assam["water_ml"], assam["temperature_c"]), (6.0, 300, 90))

    def test_rejects_sourced_member_whose_source_is_missing(self):
        cur = copy.deepcopy(self.cur)
        style = next(x for x in cur["styles"] if x["key"] == "noir-assam")
        style["sources"] = [x for x in style["sources"] if x["maison"] != "Palais des Thés"]
        with self.assertRaises(curate_mod.CurationError):
            self.curate(cur)

    def test_rejects_merging_a_sourced_recipe(self):
        cur = copy.deepcopy(self.cur)
        cur["merges"].append({"id": "green-gyokuro", "replaced_by": "green-sencha", "reason_fr": "test"})
        with self.assertRaises(curate_mod.CurationError):
            self.curate(cur)


@unittest.skipIf(Image is None, "Pillow absent")
class PhotoScriptTests(unittest.TestCase):
    def test_pipeline_crops_resizes_and_strips_metadata(self):
        src = Image.new("RGB", (3000, 4000), (90, 140, 60))  # image en portrait
        exif = Image.Exif()
        exif[0x010F] = "TestPhone"
        buf = io.BytesIO()
        src.save(buf, "JPEG", exif=exif)
        buf.seek(0)
        with tempfile.TemporaryDirectory() as tmp:
            size, px = photo_mod.write_photo(photo_mod.open_upright(buf), "green-sencha", Path(tmp))
            path = Path(tmp) / "green-sencha.webp"
            self.assertEqual(px, (1200, 800))
            self.assertEqual(curate_mod.webp_size(path), (1200, 800))
            self.assertLessEqual(size, 200_000)
            with Image.open(path) as out:
                self.assertEqual(dict(out.getexif()), {})
            self.assertEqual(curate_mod.scan_photos(Path(tmp))["green-sencha"]["width"], 1200)

    def test_too_small_refused(self):
        with self.assertRaises(photo_mod.PhotoError):
            photo_mod.make_app_photo(Image.new("RGB", (700, 500)))

    def test_scan_rejects_out_of_limits_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            Image.new("RGB", (2000, 1333)).save(Path(tmp) / "green-sencha.webp", "WEBP")
            with self.assertRaises(curate_mod.CurationError):
                curate_mod.scan_photos(Path(tmp))

    def test_check_id(self):
        entries = {e["id"]: e for e in json.loads((ROOT / "data" / "teas.json").read_text("utf-8"))["entries"]}
        merged = next(e["id"] for e in entries.values() if e["status"] == "merged")
        self.assertIsNone(photo_mod.check_id("herbal-tilleul", entries))
        self.assertIn("doublon", photo_mod.check_id(merged, entries))
        self.assertIn("inconnu", photo_mod.check_id("herbal-inconnu", entries))

    def test_credit_exception_written_and_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "photos.json"
            path.write_text(json.dumps({"credit_par_defaut": "Théothèque (IA)", "photos": {}}), "utf-8")
            photo_mod.set_credit("herbal-tilleul", "Thib", True, path)
            self.assertEqual(json.loads(path.read_text("utf-8"))["photos"]["herbal-tilleul"],
                             {"credit": "Thib", "exacte": True})
            photo_mod.set_credit("herbal-tilleul", None, False, path)
            self.assertEqual(json.loads(path.read_text("utf-8"))["photos"], {})


if __name__ == "__main__":
    unittest.main()
