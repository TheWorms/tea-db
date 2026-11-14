#!/usr/bin/env python3
"""Recherche de vraies photos r\u00e9utilisables sur Wikimedia Commons pour les fiches
sans photo (data/photos_a_rechercher.json).

    python3 scripts/commons_search.py            # \u00e9crit reports/photos-candidates.json
    python3 scripts/commons_search.py --id herbal-lavande

Pour chaque id, interroge l'API Commons (namespace File, filetype:bitmap), garde
uniquement les licences r\u00e9utilisables (domaine public, CC0, CC BY, CC BY-SA ;
jamais NC/ND/tous droits r\u00e9serv\u00e9s) et une taille suffisante apr\u00e8s recadrage 3:2
(>= 800\u00d7533 px). Classe les candidats (titre pertinent, grande taille, paysage)
et propose le meilleur dans "proposition". Sortie reproductible (tri d\u00e9terministe).

User-Agent descriptif, temporisation entre requ\u00eates : respecter l'\u00e9tiquette API
de Wikimedia (https://commons.wikimedia.org/wiki/Commons:API_etiquette).
Biblioth\u00e8que standard uniquement.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://commons.wikimedia.org/w/api.php"
UA = "tea-db-commons-search/1.0 (https://github.com/TheWorms/tea-db; recherche de photos libres pour catalogue de th\u00e9s)"

LICENCES_OK = ("public domain", "cc0", "cc by-sa", "cc by")
LICENCES_KO = ("nc", "nd", "all rights reserved", "droit moral", "no derivatives")
MIN_APRES_RECADRAGE = (800, 533)

# Requ\u00eates Commons curat\u00e9es par id (termes anglais les plus discriminants).
REQUETES = {
    "cold-the-noir-glace": ["iced tea glass ice cubes", "iced black tea"],
    "matcha-matcha-ceremonial": ["matcha powder chasen bowl whisk", "matcha tea ceremony", "ceremonial matcha powder"],
    "matcha-matcha-culinaire": ["matcha powder green tea", "matcha culinary grade powder"],
    "black-assam-ctc": ["CTC tea granules", "CTC tea"],
    "black-broken-orange-pekoe": ["broken orange pekoe tea", "BOP tea leaves"],
    "black-golden-flowery-orange-pekoe": ["flowery orange pekoe", "golden tips black tea"],
    "black-orange-pekoe": ["orange pekoe tea leaves", "OP tea"],
    "green-funmatsucha": ["funmatsucha", "powdered green tea Japan"],
    "herbal-achillee-blanche": ["Achillea millefolium dried", "yarrow dried flowers"],
    "herbal-achillee-millefeuille": ["Achillea millefolium flower dried", "Achillea millefolium umbel"],
    "herbal-ananas-seche": ["dried pineapple pieces", "Ananas comosus dried"],
    "herbal-anis-vert": ["anise seeds Pimpinella anisum", "aniseed"],
    "herbal-aubepine": ["Crataegus dried flowers", "hawthorn flowers dried"],
    "herbal-baies-d-aubepine": ["hawthorn berries dried", "Crataegus berries"],
    "herbal-baies-de-goji": ["goji berries dried", "Lycium barbarum fruit dried"],
    "herbal-baies-de-sureau": ["elderberries dried", "Sambucus nigra berries"],
    "herbal-barbe-de-mais": ["corn silk Zea mays dried", "corn silk"],
    "herbal-basilic": ["Ocimum basilicum dried leaves", "dried basil leaves"],
    "herbal-cafe-de-cereales": ["roasted barley grains", "cereal coffee roasted grain"],
    "herbal-calendula": ["Calendula officinalis dried flowers", "pot marigold dried"],
    "herbal-cannelle": ["cinnamon sticks Cinnamomum", "cinnamon bark"],
    "herbal-cardamome": ["cardamom pods Elettaria", "green cardamom pods"],
    "herbal-chardon-marie": ["Silybum marianum seeds", "milk thistle seeds"],
    "herbal-chrysantheme": ["Chrysanthemum morifolium dried flowers", "dried chrysanthemum flowers"],
    "herbal-citronnelle": ["lemongrass dried Cymbopogon citratus", "dried lemongrass"],
    "herbal-clou-de-girofle": ["cloves Syzygium aromaticum", "dried cloves"],
    "herbal-coques-de-cacao": ["cocoa husks Theobroma cacao", "cacao shell pieces"],
    "herbal-curcuma": ["dried turmeric root Curcuma longa", "turmeric rhizome dried"],
    "herbal-cynorrhodon": ["rose hips dried Rosa canina", "dried rose hips"],
    "herbal-echinacee": ["Echinacea purpurea dried", "echinacea dried flowers root"],
    "herbal-ecorce-d-orange": ["dried orange peel Citrus sinensis", "dried orange zest"],
    "herbal-fenouil": ["fennel seeds Foeniculum vulgare", "fennel seed"],
    "herbal-feuille-d-olivier": ["olive leaves dried Olea europaea", "dried olive leaves"],
    "herbal-feuille-de-bouleau": ["birch leaves dried Betula", "dried birch leaves"],
    "herbal-feuille-de-cassis": ["blackcurrant leaves dried Ribes nigrum", "dried blackcurrant leaves"],
    "herbal-feuille-de-fraisier": ["wild strawberry leaves dried Fragaria vesca", "dried strawberry leaves"],
    "herbal-feuille-de-framboisier": ["raspberry leaves dried Rubus idaeus", "dried raspberry leaves"],
    "herbal-feuille-de-guimauve": ["marshmallow leaves dried Althaea", "Althaea officinalis leaves"],
    "herbal-feuille-de-murier": ["mulberry leaves dried Morus alba", "dried mulberry leaves"],
    "herbal-fleur-d-acacia": ["black locust flowers dried Robinia", "Robinia pseudoacacia flowers dried"],
    "herbal-fleur-d-oranger": ["orange blossom dried Citrus aurantium", "dried orange flowers"],
    "herbal-fleur-de-bruyere": ["heather dried Calluna vulgaris", "dried heather flowers"],
    "herbal-fleur-de-coquelicot": ["poppy petals dried Papaver rhoeas", "dried poppy petals"],
    "herbal-fleur-de-pois-bleu": ["butterfly pea flower dried Clitoria ternatea", "Clitoria ternatea dried"],
    "herbal-fleur-de-sureau": ["elderflowers dried Sambucus nigra", "dried elderflowers"],
    "herbal-fraise-sechee": ["dried strawberry pieces", "freeze dried strawberry"],
    "herbal-gingembre": ["dried ginger root Zingiber officinale", "ginger rhizome dried"],
    "herbal-ginseng": ["ginseng root dried Panax", "dried ginseng root slices"],
    "herbal-guayusa": ["guayusa leaves dried Ilex guayusa", "Ilex guayusa dried"],
    "herbal-infusion-de-cacao": ["cocoa husk tea", "cacao nibs husk"],
    "herbal-jiaogulan": ["jiaogulan dried Gynostemma pentaphyllum", "Gynostemma pentaphyllum dried"],
    "herbal-kuding": ["kuding tea Ligustrum robustum", "Ligustrum robustum leaves dried"],
    "herbal-lavande": ["lavender dried Lavandula angustifolia", "dried lavender flowers spikes"],
    "herbal-mais-grille": ["roasted corn kernels", "roasted maize"],
    "herbal-mangue-sechee": ["dried mango pieces", "dried mango"],
    "herbal-melisse": ["lemon balm dried Melissa officinalis", "dried melissa leaves"],
    "herbal-menthe-marocaine": ["dried mint leaves Mentha spicata", "spearmint dried leaves"],
    "herbal-menthe-poivree": ["peppermint dried leaves Mentha piperita", "dried peppermint"],
    "herbal-menthe-verte": ["spearmint dried Mentha spicata", "dried spearmint leaves"],
    "herbal-moringa": ["moringa leaves dried Moringa oleifera", "dried moringa leaves"],
    "herbal-mugicha-orge-grillee": ["mugicha roasted barley", "roasted barley grains tea"],
    "herbal-ortie": ["nettle leaves dried Urtica dioica", "dried stinging nettle"],
    "herbal-osmanthus-osmanthe": ["osmanthus flowers dried Osmanthus fragrans", "dried osmanthus"],
    "herbal-passiflore": ["passionflower dried Passiflora incarnata", "Passiflora incarnata dried"],
    "herbal-petales-de-rose": ["dried rose petals Rosa damascena", "rose petals dried"],
    "herbal-pissenlit": ["dandelion root dried Taraxacum", "dried dandelion root leaves"],
    "herbal-poivre-rose": ["pink peppercorns dried Schinus molle", "dried pink pepper"],
    "herbal-pomme-sechee": ["dried apple pieces", "dried apple rings"],
    "herbal-racine-de-chicoree": ["roasted chicory root Cichorium intybus", "chicory coffee"],
    "herbal-racine-de-guimauve": ["marshmallow root dried Althaea officinalis", "dried marshmallow root"],
    "herbal-racine-de-reglisse": ["licorice root dried Glycyrrhiza glabra", "dried licorice root"],
    "herbal-reine-des-pres": ["meadowsweet dried Filipendula ulmaria", "Filipendula ulmaria dried"],
    "herbal-romarin": ["dried rosemary Salvia rosmarinus", "rosemary dried leaves"],
    "herbal-sauge": ["sage leaves dried Salvia officinalis", "dried sage leaves"],
    "herbal-sobacha-sarrasin-torrefie": ["sobacha roasted buckwheat", "roasted buckwheat grains"],
    "herbal-thym": ["dried thyme Thymus vulgaris", "thyme dried leaves"],
    "herbal-tilleul": ["linden flowers dried Tilia", "dried linden blossom"],
    "herbal-tisane-au-citron": ["lemon verbena dried Aloysia citrodora", "herbal tea lemon dried"],
    "herbal-tisane-de-fleurs": ["dried herbal tea flowers blend", "herbal tea mixture dried flowers"],
    "herbal-tisane-de-noel": ["christmas tea dried spices blend", "mulled tea spices dried"],
    "herbal-tisane-digestive": ["digestive herbal tea dried blend", "fennel anise mint herbal tea dried"],
    "herbal-tisane-du-soir": ["evening herbal tea dried blend", "linden chamomile herbal tea dried"],
    "herbal-tisane-gingembre-citron": ["ginger lemon herbal tea dried", "dried ginger lemon tea"],
    "herbal-tisane-menthe-citron": ["mint lemon herbal tea dried", "dried mint lemon peel"],
    "herbal-tisane-pomme-cannelle": ["apple cinnamon tea dried", "dried apple cinnamon pieces"],
    "herbal-tisane-reglisse-menthe": ["licorice mint herbal tea dried", "dried licorice mint leaves"],
    "herbal-tulsi": ["holy basil dried Ocimum sanctum", "tulsi dried leaves"],
    "herbal-tulsi-krishna": ["Ocimum sanctum krishna dried", "tulsi krishna purple leaves dried"],
    "herbal-tulsi-rama": ["tulsi rama dried leaves", "Ocimum sanctum rama"],
    "herbal-tulsi-vana": ["tulsi vana dried", "Ilex? no - tulsi vana leaves"],
    "herbal-valeriane": ["valerian root dried Valeriana officinalis", "dried valerian root"],
    "herbal-verveine-citronnelle": ["lemon verbena dried leaves Aloysia citrodora", "Aloysia citrodora dried"],
    "herbal-yaupon": ["yaupon leaves dried Ilex vomitoria", "Ilex vomitoria dried"],
    "herbal-zeste-de-citron": ["dried lemon zest Citrus limon", "dried lemon peel strips"],
    "oolong-ba-xian": ["ba xian oolong tea leaves", "oolong tea twisted leaves"],
    "oolong-bai-ji-guan": ["bai ji guan oolong tea", "bai ji guan leaves"],
    "oolong-baozhong": ["baozhong tea leaves", "pouchong tea"],
    "oolong-bei-dou": ["bei dou oolong tea", "wuyi oolong tea leaves"],
    "oolong-da-hong-pao": ["da hong pao tea leaves", "Da Hong Pao"],
    "oolong-dan-cong-song-zhong": ["dan cong tea leaves", "phoenix dan cong oolong"],
    "oolong-dong-ding-torrefie": ["dong ding tea", "roasted dong ding oolong rolled"],
    "oolong-feng-huang-shui-xian": ["shui xian oolong tea leaves", "feng huang shui xian"],
    "oolong-formosa-oolong": ["formosa oolong tea", "taiwanese oolong tea leaves"],
    "oolong-huang-zhi-xiang": ["huang zhi xiang oolong tea", "dan cong tea leaves"],
    "oolong-jin-fo": ["jin fo oolong tea", "wuyi oolong tea leaves"],
    "oolong-oolong-dragon-noir": ["oolong tea leaves dark roasted", "wuyi oolong"],
    "oolong-oriental-beauty": ["oriental beauty oolong", "dong fang mei ren tea"],
    "oolong-phoenix-dan-cong": ["phoenix dan cong tea leaves", "dan cong oolong"],
    "oolong-qi-dan": ["qi dan oolong tea", "wuyi oolong tea leaves"],
    "oolong-qi-lan": ["qi lan oolong tea", "wuyi oolong tea leaves"],
    "oolong-qi-zhong": ["qi zhong oolong tea", "wuyi oolong tea leaves"],
    "oolong-red-oolong": ["red oolong tea rolled", "hong oolong tea"],
    "oolong-ruby-oolong": ["ruby oolong tea", "hong oolong rolled tea"],
    "oolong-shui-jin-gui": ["shui jin gui oolong tea", "wuyi oolong tea leaves"],
    "oolong-tie-guan-yin-torrefie": ["tie guan yin roasted tea", "roasted tieguanyin rolled"],
    "oolong-tie-luo-han": ["tie luo han oolong tea", "wuyi oolong tea leaves"],
    "oolong-wenshan-baozhong": ["wenshan baozhong tea", "pouchong tea leaves"],
    "oolong-wu-yi-yan-cha": ["wuyi yan cha tea leaves", "yancha oolong"],
    "oolong-wuyi-rou-gui": ["rou gui wuyi oolong tea", "cinnamon tea wuyi"],
    "oolong-wuyi-shui-xian": ["wuyi shui xian tea", "shui xian oolong leaves"],
    "oolong-xing-ren-xiang": ["xing ren xiang oolong tea", "dan cong tea leaves"],
    "oolong-ya-shi-xiang": ["ya shi xiang oolong tea", "dan cong tea leaves"],
    "oolong-yu-lan-xiang": ["yu lan xiang oolong tea", "magnolia oolong dan cong"],
    "oolong-zhi-lan-xiang": ["zhi lan xiang oolong tea", "dan cong tea leaves"],
    "pu_erh-ba-da-sheng": ["pu-erh cake ba da shan", "pu erh sheng cake"],
    "pu_erh-bamboo-pu-erh": ["bamboo pu erh cylinder", "pu erh in bamboo"],
    "pu_erh-bing-dao": ["bing dao pu erh cake", "pu erh cake"],
    "pu_erh-bulang-mountain": ["bulang pu erh cake", "pu erh sheng cake leaves"],
    "pu_erh-gedeng-sheng": ["gedeng pu erh cake", "pu erh cake"],
    "pu_erh-golden-bud-pu-erh": ["golden bud pu erh", "pu erh golden buds loose"],
    "pu_erh-huazhu-liangzi": ["huazhu liangzi pu erh cake", "pu erh cake"],
    "pu_erh-jin-cha": ["jin cha pu erh mushroom tuo", "pu erh mushroom shape"],
    "pu_erh-jingmai-sheng": ["jingmai pu erh cake", "pu erh sheng cake"],
    "pu_erh-lao-ban-zhang": ["lao ban zhang pu erh cake", "pu erh cake"],
    "pu_erh-lao-man-e": ["lao man e pu erh cake", "pu erh cake"],
    "pu_erh-lincang-sheng": ["lincang pu erh cake", "pu erh cake"],
    "pu_erh-manzhuan-sheng": ["manzhuan pu erh cake", "pu erh cake"],
    "pu_erh-menghai-7542": ["menghai 7542 pu erh cake", "pu erh cake 7542"],
    "pu_erh-menghai-8582": ["menghai 8582 pu erh cake", "pu erh cake"],
    "pu_erh-mengku-sheng": ["mengku pu erh cake", "pu erh cake"],
    "pu_erh-nannuo-mountain": ["nannuo pu erh cake", "pu erh cake"],
    "pu_erh-pasha-sheng": ["pasha pu erh cake", "pu erh cake"],
    "pu_erh-pu-erh-mini-tuo-cha": ["mini tuocha", "mini tuo cha"],
    "pu_erh-purple-bud-pu-erh": ["purple pu erh buds", "zi ya pu erh"],
    "pu_erh-sheng-pu-erh": ["sheng pu erh cake", "raw pu erh cake"],
    "pu_erh-tuo-cha": ["tuocha tuo cha", "pu erh tuocha nest"],
    "pu_erh-xiaguan-tuocha": ["xiaguan tuocha", "tuocha"],
    "pu_erh-yibang-sheng": ["yibang pu erh cake", "pu erh cake"],
    "pu_erh-yiwu-gushu": ["yiwu gushu pu erh cake", "yiwu pu erh cake"],
    "pu_erh-yiwu-sheng": ["yiwu pu erh cake", "pu erh sheng cake"],
    "pu_erh-zhuan-cha": ["pu erh brick zhuan cha", "tea brick"],
    "white-bai-mudan": ["bai mu dan white tea", "white peony tea buds leaves"],
    "white-bai-mudan-vieilli": ["aged bai mu dan white tea", "white tea aged cake"],
    "white-galette-de-the-blanc-vieilli": ["aged white tea cake", "white pu erh cake broken"],
    "white-gong-mei": ["gong mei white tea", "white tea gong mei"],
    "white-moonlight-white": ["moonlight white tea", "yue guang bai white tea"],
    "white-shou-mei": ["shou mei white tea", "white tea shou mei"],
    "white-shou-mei-vieilli": ["aged shou mei white tea", "old white tea"],
    "yellow-huang-da-cha": ["huang da cha yellow tea", "yellow tea leaves"],
    "black-assam-golden-tips": ["assam golden tips tea", "assam tea golden buds"],
    "black-darjeeling-castleton": ["darjeeling tea leaves", "castleton tea garden darjeeling"],
    "black-golden-monkey": ["golden monkey tea", "jin hou tea leaves"],
    "black-yunnan-gold": ["yunnan gold tea", "dian hong golden"],
    "black-yunnan-gold-tips": ["yunnan golden tips tea", "dian hong tips"],
    "black-yunnan-golden-buds": ["yunnan golden buds tea", "dian hong golden bud"],
    "black-yunnan-golden-needle": ["yunnan golden needle", "jin zhen dian hong"],
    "dark-anhua-hei-cha": ["anhua hei cha", "heicha anhua dark tea", "dark tea anhua loose"],
    "dark-dark-tea-sichuan": ["sichuan dark tea brick", "ya an dark tea", "sichuan biancha"],
    "dark-fu-zhuan": ["fuzhuan tea", "anhua fuzhuan", "fu brick tea"],
    "dark-hei-zhuan": ["heizhuan brick", "hei zhuan brick", "black brick tea heicha"],
    "dark-hua-zhuan": ["huazhuan brick", "hua zhuan brick tea", "flower brick fu tea"],
    "dark-hubei-qing-zhuan": ["qingzhuan brick", "qing zhuan brick", "hubei green brick tea"],
    "dark-kang-zhuan": ["kangzhuan brick", "kang zhuan brick", "kang brick tea"],
    "dark-liu-an-dark-tea": ["liu an gua pian", "liu'an dark tea", "liu an basket"],
    "dark-liu-bao": ["liubao tea", "liu bao tea", "liu bao basket leaves"],
    "dark-qian-liang-cha": ["qianliang tea", "qian liang cha", "thousand liang tea roll"],
    "dark-tian-jian": ["tianjian tea", "tian jian tea", "tian jian basket"],
    "dark-ya-an-zang-cha": ["zangcha brick", "zang cha brick", "tibetan tea brick ya'an"],
    "green-genmaicha-matcha": ["genmaicha matcha", "genmaicha green tea rice"],
    "green-gunpowder": ["gunpowder tea", "green tea gunpowder pellets"],
    "green-konacha": ["konacha", "konacha powder green tea"],
    "green-kukicha-grille": ["kukicha", "roasted kukicha stems"],
    "green-kyobancha": ["kyobancha", "bancha kyobancha leaves"],
    "green-moroccan-mint": ["moroccan mint tea", "gunpowder mint tea"],
    "herbal-honeybush": ["honeybush tea", "Cyclopia honeybush"],
    "herbal-honeybush-vanille": ["honeybush vanilla tea", "honeybush"],
    "herbal-rooibos-vert": ["green rooibos", "unfermented rooibos Aspalathus"],
}

# Retirons la requ\u00eate parasite de tulsi-vana.
REQUETES["herbal-tulsi-vana"] = ["tulsi vana dried", "Ocimum gratissimum dried leaves"]


def post_crop_size(w: int, h: int) -> tuple[int, int]:
    """Taille apr\u00e8s recadrage 3:2 paysage de scripts/add_photo.py."""
    ratio = 1200 / 800
    if w / h > ratio:
        return round(h * ratio), h
    return w, round(w / ratio)


def licence_ok(short: str) -> bool:
    s = short.lower()
    if any(k in s for k in LICENCES_KO):
        return False
    return any(k in s for k in LICENCES_OK)


def api(params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": "2"}
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def search(query: str, limit: int = 15) -> list[dict]:
    data = api({
        "action": "query", "generator": "search",
        "gsrsearch": f"{query} filetype:bitmap", "gsrnamespace": "6", "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": "1600",
    })
    return data.get("query", {}).get("pages", [])


def score(title: str, w: int, h: int, query: str) -> float:
    t = unicodedata.normalize("NFKD", title.lower())
    terms = [x for x in query.lower().split() if len(x) > 3]
    hits = sum(1 for x in terms if x in t)
    s = hits * 10
    cw, ch = post_crop_size(w, h)
    s += min(cw * ch / 1e6, 8)          # grande image : un peu mieux
    if w >= h:
        s += 2                            # paysage privil\u00e9gi\u00e9
    for bonus in ("dried", "loose", "leaves", "powder", "tea", "cake", "brick"):
        if bonus in t:
            s += 1
    for malus in ("packaging", "package", "box", "bag", "sachet", "label", "shop", "store",
                  "brand", "cafe", "caf\u00e9", "coffee", "frappe", "espresso", "smoothie",
                  "bakery", "supermarket", "restaurant", "company", "logo", "menu",
                  "storefront", "wrapper", "tea bag", "teabag"):
        if malus in t:
            s -= 8
    if "latte" in t:
        s -= 4
    return s


def candidates_for(tea_id: str, queries: list[str]) -> list[dict]:
    seen, out = set(), []
    for q in queries:
        try:
            pages = search(q)
        except Exception as exc:  # r\u00e9seau : on garde ce qu'on a
            print(f"  {tea_id} / {q!r} : erreur API ({exc})", file=sys.stderr)
            continue
        time.sleep(0.35)
        for p in pages:
            title = p.get("title", "")
            if title in seen:
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") not in ("image/jpeg", "image/png"):
                continue
            em = ii.get("extmetadata", {})
            lic = (em.get("LicenseShortName", {}) or {}).get("value", "")
            if not licence_ok(lic):
                continue
            w, h = ii.get("width", 0), ii.get("height", 0)
            cw, ch = post_crop_size(w, h)
            if cw < MIN_APRES_RECADRAGE[0] or ch < MIN_APRES_RECADRAGE[1]:
                continue
            seen.add(title)
            out.append({
                "title": title,
                "page": ii.get("descriptionurl", ""),
                "artist": (em.get("Artist", {}) or {}).get("value", "") or "",
                "license": lic,
                "license_url": (em.get("LicenseUrl", {}) or {}).get("value", "") or "",
                "width": w, "height": h,
                "thumb": ii.get("thumburl", ""),
                "query": q,
                "score": round(score(title, w, h, q), 2),
            })
    out.sort(key=lambda c: (-c["score"], c["title"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--id", help="ne traiter qu'un seul id")
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "photos-candidates.json")
    args = ap.parse_args(argv)

    demandes = json.loads((ROOT / "data" / "photos_a_rechercher.json").read_text(encoding="utf-8"))["demandes"]
    if args.id:
        demandes = [d for d in demandes if d["id"] == args.id]
        if not demandes:
            print(f"id inconnu : {args.id}", file=sys.stderr)
            return 1

    result = {}
    for i, d in enumerate(demandes, 1):
        queries = REQUETES.get(d["id"]) or [d["nom"]]
        cands = candidates_for(d["id"], queries)
        result[d["id"]] = {
            "nom": d["nom"], "famille": d["famille"], "priorite": d["priorite"],
            "montrer": d["montrer"], "candidats": cands[:8],
            "proposition": cands[0] if cands else None,
        }
        prop = result[d["id"]]["proposition"]
        print(f"[{i}/{len(demandes)}] {d['id']}: {len(cands)} candidats"
              + (f" -> {prop['title']} ({prop['license']})" if prop else " -> introuvable"))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_prop = sum(1 for v in result.values() if v["proposition"])
    print(f"\n{len(result)} ids trait\u00e9s, {n_prop} avec proposition, {len(result) - n_prop} introuvables. -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
