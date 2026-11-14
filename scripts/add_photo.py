#!/usr/bin/env python3
"""Met une image au format de l'appli et la range dans le catalogue.

    python3 scripts/add_photo.py herbal-tilleul ~/Images/tilleul.png
    python3 scripts/add_photo.py --lot dossier/       # images nommées <id>.png, .jpg ou .webp
    python3 scripts/curate.py                         # rebranche les fiches sur leur photo

Produit docs/assets/photos/catalogue/<id>.webp : recadrée au centre en 3:2
(paysage), 1200 × 800 px (jamais agrandie ; minimum 800 × 533), WebP d'environ
100 Ko et jamais plus de 200 Ko, sans métadonnées EXIF (position GPS, modèle de
l'appareil).

Par défaut l'image est une illustration (crédit « Théothèque (IA) »,
photo_exacte = false). Pour une vraie photo du produit : --credit "Thib" --exacte.

--position règle le recadrage d'une image trop haute ou trop large :
0 = haut (ou gauche), 50 = centre, 100 = bas (ou droite).

Le dépôt est destiné à être public : n'y mettez que des images que vous avez le
droit de publier. Nécessite Pillow (Arch : pacman -S python-pillow).
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "data" / "teas.json"
PHOTOS_PATH = ROOT / "data" / "photos.json"
PHOTO_DIR = ROOT / "docs" / "assets" / "photos" / "catalogue"
TARGET = (1200, 800)
MINIMUM = (800, 533)
TARGET_BYTES = 120_000
MAX_BYTES = 200_000
SOURCE_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_CREDIT = 60


class PhotoError(Exception):
    pass


def open_upright(source):
    """Ouvre une image (chemin ou flux), applique la rotation EXIF, renvoie du RGB."""
    from PIL import Image, ImageOps

    with Image.open(source) as src:
        return ImageOps.exif_transpose(src).convert("RGB")


def crop_3_2(img, position: int = 50):
    """Recadre en 3:2 paysage. position : 0 = haut/gauche, 50 = centre, 100 = bas/droite."""
    w, h = img.size
    ratio = TARGET[0] / TARGET[1]
    if w / h > ratio:                      # trop large : on coupe à gauche et à droite
        new_w = round(h * ratio)
        left = round((w - new_w) * position / 100)
        return img.crop((left, 0, left + new_w, h))
    new_h = round(w / ratio)               # trop haute : on coupe en haut et en bas
    top = round((h - new_h) * position / 100)
    return img.crop((0, top, w, top + new_h))


def encode_webp(img) -> tuple[bytes, int]:
    """WebP visé ~100 Ko : qualité 82, abaissée jusqu'à 60 si besoin ; refus au-delà de 200 Ko."""
    for quality in (82, 76, 70, 65, 60):
        buf = io.BytesIO()
        # Sans exif= ni icc_profile= : aucune métadonnée n'est recopiée.
        img.save(buf, "WEBP", quality=quality, method=6)
        data = buf.getvalue()
        if len(data) <= TARGET_BYTES:
            return data, quality
    if len(data) > MAX_BYTES:
        raise PhotoError(f"photo trop lourde même en qualité 60 ({len(data) // 1000} Ko)")
    return data, quality


def make_app_photo(img, position: int = 50) -> tuple[bytes, tuple[int, int], int]:
    from PIL import Image

    img = crop_3_2(img, position)
    if img.width < MINIMUM[0] or img.height < MINIMUM[1]:
        raise PhotoError(f"photo trop petite : {img.width}×{img.height} px après recadrage, "
                         f"minimum {MINIMUM[0]}×{MINIMUM[1]}")
    if img.width > TARGET[0]:
        img = img.resize(TARGET, Image.Resampling.LANCZOS)
    data, quality = encode_webp(img)
    return data, img.size, quality


def write_photo(img, tea_id: str, photo_dir: Path = PHOTO_DIR, position: int = 50) -> tuple[int, tuple[int, int]]:
    data, size, _ = make_app_photo(img, position)
    photo_dir.mkdir(parents=True, exist_ok=True)
    (photo_dir / f"{tea_id}.webp").write_bytes(data)
    return len(data), size


def remove_photo(tea_id: str, photo_dir: Path = PHOTO_DIR) -> None:
    (photo_dir / f"{tea_id}.webp").unlink(missing_ok=True)


def load_entries() -> dict[str, dict]:
    with open(CATALOG_PATH, encoding="utf-8") as fh:
        return {e["id"]: e for e in json.load(fh)["entries"]}


def check_id(tea_id: str, entries: dict[str, dict]) -> str | None:
    """Message d'erreur si l'id ne peut pas recevoir de photo, sinon None."""
    entry = entries.get(tea_id)
    if entry is None:
        close = [i for i in entries if tea_id.split("-")[-1] in i][:8]
        return f"id inconnu : {tea_id}" + (f" (proches : {', '.join(close)})" if close else "")
    if entry.get("status") == "merged":
        return f"{tea_id} est un doublon : utilisez {entry['replaced_by']}"
    return None


def set_credit(tea_id: str, credit: str | None, exacte: bool, path: Path = PHOTOS_PATH) -> None:
    """Enregistre l'exception de crédit, ou la retire pour revenir au crédit par défaut."""
    with open(path, encoding="utf-8") as fh:
        conf = json.load(fh)
    photos = conf.setdefault("photos", {})
    if credit or exacte:
        photos[tea_id] = {"credit": credit or conf["credit_par_defaut"], "exacte": exacte}
    else:
        photos.pop(tea_id, None)
    conf["photos"] = dict(sorted(photos.items()))
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(conf, ensure_ascii=False, indent=2) + "\n")


def add_one(tea_id: str, image: Path, entries: dict, args) -> bool:
    problem = check_id(tea_id, entries)
    if problem:
        print(f"{image.name} : {problem}", file=sys.stderr)
        return False
    full = PHOTO_DIR / f"{tea_id}.webp"
    if full.exists() and not args.force:
        print(f"{full.relative_to(ROOT)} existe déjà : --force pour remplacer", file=sys.stderr)
        return False
    try:
        size_bytes, size_px = write_photo(open_upright(image), tea_id, PHOTO_DIR, args.position)
    except PhotoError as exc:
        print(f"{image.name} refusée : {exc}", file=sys.stderr)
        return False
    except OSError as exc:
        print(f"{image.name} illisible : {exc}", file=sys.stderr)
        return False
    set_credit(tea_id, args.credit, args.exacte)
    name = entries[tea_id]["name"]
    print(f"{name} : {full.relative_to(ROOT)} ({size_px[0]}×{size_px[1]} px, {size_bytes // 1000} Ko)")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Met une image au format de l'appli.")
    parser.add_argument("tea_id", nargs="?", help="id de la fiche, ex. herbal-tilleul")
    parser.add_argument("image", nargs="?", type=Path, help="image source (PNG, JPEG, WebP…)")
    parser.add_argument("--lot", type=Path, metavar="DOSSIER",
                        help="traiter toutes les images d'un dossier, nommées <id>.png, .jpg ou .webp")
    parser.add_argument("--credit", default=None, help="crédit affiché (défaut : celui de data/photos.json)")
    parser.add_argument("--exacte", action="store_true", help="vraie photo du produit (photo_exacte = true)")
    parser.add_argument("--position", type=int, default=50, help="recadrage 0-100 (défaut 50 = centre)")
    parser.add_argument("--force", action="store_true", help="remplacer une photo existante")
    args = parser.parse_args(argv)

    try:
        import PIL  # noqa: F401
    except ImportError:
        print("Pillow manquant : sudo pacman -S python-pillow (ou pip install Pillow)", file=sys.stderr)
        return 2
    if not 0 <= args.position <= 100:
        print("--position doit être entre 0 et 100", file=sys.stderr)
        return 1
    if args.credit and len(args.credit) > MAX_CREDIT:
        print(f"--credit : {MAX_CREDIT} caractères au plus", file=sys.stderr)
        return 1

    entries = load_entries()
    if args.lot:
        if args.tea_id or args.image:
            print("--lot s'utilise seul, sans id ni image", file=sys.stderr)
            return 1
        if not args.lot.is_dir():
            print(f"dossier introuvable : {args.lot}", file=sys.stderr)
            return 1
        files = sorted(f for f in args.lot.iterdir() if f.suffix.lower() in SOURCE_EXT)
        if not files:
            print(f"aucune image .png, .jpg ou .webp dans {args.lot}", file=sys.stderr)
            return 1
        done = sum(add_one(f.stem, f, entries, args) for f in files)
        print(f"{done} image(s) ajoutée(s) sur {len(files)}.")
        ok = done == len(files)
    else:
        if not args.tea_id or not args.image:
            parser.error("donner un id et une image, ou --lot DOSSIER")
        if not args.image.is_file():
            print(f"fichier introuvable : {args.image}", file=sys.stderr)
            return 1
        ok = add_one(args.tea_id, args.image, entries, args)
    if ok or args.lot:
        print("Lancer ensuite : python3 scripts/curate.py")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
