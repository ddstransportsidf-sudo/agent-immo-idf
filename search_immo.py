#!/usr/bin/env python3
"""
Agent Immo IDF - Recherche appartements dernier etage
Zones : Val-d'Oise (95), Nord 92, villes limitrophes 60/78
Filtres : dernier etage, hors viager/LMNP, <=110k eur, >=20m2, proche gare
Envoi : Telegram
"""

import json
import urllib.request
import gzip
import time
import unicodedata
from datetime import datetime

BOT_TOKEN = "8728701920:AAFovP3Xrr1L3BYqA4YaeVyOYvkv3j83eIc"
CHAT_ID   = "1275491129"

VIAGER_KEYWORDS = ["viager", "bouquet", "rente viagere", "viager occupe", "viager libre"]
LMNP_KEYWORDS = [
    "lmnp", "loueur meuble", "residence de services", "residence etudiante",
    "residence senior", "residence tourisme", "ehpad", "bail commercial",
    "investissement locatif meuble", "residence geree", "rendement garanti",
    "loyer garanti", "residence affaire", "residence hoteliere",
    "specialiste de l investissement", "rendement securise",
]

CITIES_WITH_STATIONS = {
    "argenteuil": "Transilien J/L",
    "bezons": "RER A",
    "cormeilles-en-parisis": "Transilien J",
    "herblay-sur-seine": "Transilien J",
    "conflans-sainte-honorine": "Transilien J",
    "acheres": "Transilien J/L",
    "maisons-laffitte": "Transilien J / RER A",
    "sartrouville": "Transilien J / RER A",
    "houilles": "Transilien J / RER A",
    "carrieres-sur-seine": "Transilien L",
    "franconville": "Transilien H",
    "ermont": "Transilien H",
    "sannois": "Transilien H",
    "saint-gratien": "Transilien H",
    "enghien-les-bains": "Transilien H",
    "montmorency": "Tramway T5",
    "deuil-la-barre": "Transilien H",
    "taverny": "Transilien H",
    "bessancourt": "Transilien H",
    "cergy": "RER A / Transilien L",
    "pontoise": "RER C / Transilien H",
    "saint-ouen-l-aumone": "RER C / Transilien H/L",
    "osny": "RER C",
    "eragny": "RER A",
    "garges-les-gonesse": "RER D",
    "sarcelles": "RER D / Tramway T5",
    "villiers-le-bel": "RER D",
    "gonesse": "RER B/D",
    "goussainville": "RER D",
    "viarmes": "Transilien H",
    "persan": "Transilien H",
    "beaumont-sur-oise": "Transilien H",
    "chars": "Transilien J",
    "pierrelaye": "Transilien H",
    "saint-brice-sous-foret": "Transilien H",
    "soisy-sous-montmorency": "Transilien H",
    "domont": "Transilien H",
    "roissy-en-france": "RER B (CDG)",
    "louvres": "RER B",
    "survilliers": "RER D",
    "fosses": "RER D",
    "chambly": "Transilien H",
    "bruyeres-sur-oise": "Transilien H",
    "bernes-sur-oise": "Transilien H",
    "asnieres-sur-seine": "Transilien J / RER C",
    "colombes": "Transilien L/J",
    "bois-colombes": "Transilien J",
    "la garenne-colombes": "Transilien J / RER A",
    "gennevilliers": "Metro 13",
    "villeneuve-la-garenne": "Metro 13",
    "clichy": "Metro 13",
    "courbevoie": "Transilien L / RER E",
    "nanterre": "RER A / Transilien L/U",
    "levallois-perret": "Metro 3",
}


def normalize(s):
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def get_station(city):
    city_n = normalize(city)
    for known, gare in CITIES_WITH_STATIONS.items():
        kn = normalize(known)
        if city_n == kn or city_n in kn or kn in city_n:
            return gare
    return None


def contains_keywords(text, keywords):
    t = normalize(text)
    return any(normalize(kw) in t for kw in keywords)


def fetch_lbc_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            try:
                raw = gzip.decompress(raw)
            except Exception:
                pass
            content = raw.decode("utf-8", errors="replace")
        marker = 'id="__NEXT_DATA__"'
        start = content.find(marker)
        if start == -1:
            return [], 0
        start = content.find(">", start) + 1
        end = content.find("</script>", start)
        data = json.loads(content[start:end])
        search = data.get("props", {}).get("pageProps", {}).get("searchData", {})
        return search.get("ads", []), search.get("total", 0)
    except Exception as e:
        print(f"  [ERREUR fetch] {url} - {e}")
        return [], 0


def parse_ad(raw):
    floor_num = nb_floors = None
    rooms = square = ""
    for attr in raw.get("attributes", []):
        k = attr.get("key", "")
        v = attr.get("value", "")
        vl = attr.get("value_label", "") or v
        if k == "floor_number":
            try:
                floor_num = int(v)
            except ValueError:
                pass
        elif k == "nb_floors_building":
            try:
                nb_floors = int(v)
            except ValueError:
                pass
        elif k == "rooms":
            rooms = vl
        elif k == "square":
            square = vl
    price_list = raw.get("price", [])
    return {
        "id": raw.get("list_id"),
        "title": raw.get("subject", ""),
        "price": price_list[0] if price_list else None,
        "city": raw.get("location", {}).get("city", ""),
        "zipcode": raw.get("location", {}).get("zipcode", ""),
        "square": square,
        "rooms": rooms,
        "floor_num": floor_num,
        "nb_floors": nb_floors,
        "url": f"https://www.leboncoin.fr/ad/ventes_immobilieres/{raw.get('list_id')}",
    }


def is_last_floor(ad):
    fn, nf = ad["floor_num"], ad["nb_floors"]
    return fn is not None and nf is not None and fn > 0 and fn == nf


def search_lbc(locations_param, label):
    results = []
    page = 1
    while True:
        url = (
            f"https://www.leboncoin.fr/recherche"
            f"?category=9&locations={locations_param}"
            f"&real_estate_type=2&price=0-110000&square=20-max"
            f"&page={page}&kst=k"
        )
        ads_raw, total = fetch_lbc_page(url)
        if not ads_raw:
            break
        for raw in ads_raw:
            ad = parse_ad(raw)
            if not ad["price"] or ad["price"] > 110000:
                continue
            if contains_keywords(ad["title"], VIAGER_KEYWORDS):
                continue
            if contains_keywords(ad["title"], LMNP_KEYWORDS):
                continue
            if not is_last_floor(ad):
                continue
            gare = get_station(ad["city"])
            if not gare:
                continue
            ad["gare"] = gare
            results.append(ad)
        if page * 35 >= total or page >= 7:
            break
        page += 1
        time.sleep(1.5)
    print(f"  {label}: {len(results)} annonce(s)")
    return results


def send_telegram(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    body = json.dumps({
        "chat_id": CHAT_ID,
        "parse_mode": "HTML",
        "text": text,
        "disable_web_page_preview": True,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read()).get("ok", False)
    except Exception as e:
        print(f"  [Telegram ERREUR] {e}")
        return False


def fmt(p):
    return f"{p:,}".replace(",", " ")


def main():
    today = datetime.now().strftime("%d/%m/%Y")
    print(f"\n=== Agent Immo IDF - {today} ===\n")

    send_telegram(
        f"\U0001f3e0 <b>Recherche immo - {today}</b>\n"
        f"\U0001f4cd Val-d'Oise (95) + limite 60/78 + Nord du 92\n"
        f"\U0001f4b0 Budget max : 110 000 EUR\n"
        f"\U0001f4d0 Surface min : 20m2\n"
        f"\U0001f3e2 Dernier etage uniquement\n"
        f"\U0001f6ab Pas de viager ni LMNP\n"
        f"\U0001f689 Proche gare\n"
        f"Sites consultes : LeBonCoin"
    )
    time.sleep(1)

    res_95 = search_lbc("d_95", "LeBonCoin 95")
    res_92 = search_lbc(
        "Asni%C3%A8res-sur-Seine_92600,Colombes_92700,Gennevilliers_92230,"
        "Villeneuve-la-Garenne_92390,Clichy_92110,Bois-Colombes_92270,"
        "La+Garenne-Colombes_92250,Courbevoie_92400,Nanterre_92000,Levallois-Perret_92300",
        "LeBonCoin Nord 92"
    )
    res_border = search_lbc(
        "Conflans-Sainte-Honorine_78700,Sartrouville_78500,Houilles_78800,"
        "Ach%C3%A8res_78260,Maisons-Laffitte_78600,Persan_95340,"
        "Beaumont-sur-Oise_95260,Chambly_60230",
        "LeBonCoin Limitrophes 60/78"
    )

    seen = set()
    all_listings = []
    for lst in [res_95, res_92, res_border]:
        for ad in lst:
            if ad["id"] not in seen:
                seen.add(ad["id"])
                all_listings.append(ad)

    all_listings.sort(key=lambda x: x["price"])
    print(f"\nTotal unique : {len(all_listings)} annonce(s)\n")

    if not all_listings:
        send_telegram("\u274c Aucune annonce trouvee.")
    else:
        for ad in all_listings:
            try:
                sq = int("".join(filter(str.isdigit, str(ad["square"])[:5])))
                stxt = f"{sq}m2 - {fmt(round(ad['price'] / sq))} EUR/m2"
            except Exception:
                stxt = str(ad["square"])
            msg = (
                f"\U0001f195 <b>{ad['title']}</b>\n"
                f"\U0001f4b0 {fmt(ad['price'])} EUR ({stxt})\n"
                f"\U0001f4d0 {ad['rooms']} piece(s)\n"
                f"\U0001f4cd {ad['city']} ({ad['zipcode']})\n"
                f"\U0001f3e2 Dernier etage ({ad['floor_num']}/{ad['nb_floors']})\n"
                f"\U0001f689 Gare proche : {ad['gare']}\n"
                f"\U0001f517 <a href=\"{ad['url']}\">Voir sur LeBonCoin</a>"
            )
            send_telegram(msg)
            time.sleep(0.6)

    send_telegram(
        f"\U0001f4ca <b>Resume - {today}</b>\n\n"
        f"LeBonCoin 95 : {len(res_95)} annonce(s)\n"
        f"LeBonCoin Nord 92 : {len(res_92)} annonce(s)\n"
        f"LeBonCoin Limitrophes 60/78 : {len(res_border)} annonce(s)\n\n"
        f"<b>Total : {len(all_listings)} annonce(s)</b>"
    )
    print("=== Termine ===")


if __name__ == "__main__":
    main()
