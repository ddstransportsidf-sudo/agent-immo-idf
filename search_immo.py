#!/usr/bin/env python3
"""
Agent Immo IDF - Recherche appartements dernier etage
Comparaison nouvelles vs deja connues - persistence via seen_ids.json
"""

import json, urllib.request, gzip, time, unicodedata, os
from datetime import datetime

BOT_TOKEN = "8728701920:AAFovP3Xrr1L3BYqA4YaeVyOYvkv3j83eIc"
CHAT_ID   = "1275491129"
SEEN_FILE = "seen_ids.json"

VIAGER_KW = ["viager","bouquet","rente viagere","viager occupe","viager libre"]
LMNP_KW   = [
    "lmnp","loueur meuble","residence de services","residence etudiante",
    "residence senior","residence tourisme","ehpad","bail commercial",
    "investissement locatif meuble","residence geree","rendement garanti",
    "loyer garanti","residence affaire","residence hoteliere",
    "specialiste de l investissement","rendement securise",
]
CITIES = {
    "argenteuil":"Transilien J/L","bezons":"RER A","cormeilles-en-parisis":"Transilien J",
    "herblay-sur-seine":"Transilien J","conflans-sainte-honorine":"Transilien J",
    "acheres":"Transilien J/L","maisons-laffitte":"Transilien J / RER A",
    "sartrouville":"Transilien J / RER A","houilles":"Transilien J / RER A",
    "carrieres-sur-seine":"Transilien L","franconville":"Transilien H",
    "ermont":"Transilien H","sannois":"Transilien H","saint-gratien":"Transilien H",
    "enghien-les-bains":"Transilien H","montmorency":"Tramway T5",
    "deuil-la-barre":"Transilien H","taverny":"Transilien H","bessancourt":"Transilien H",
    "cergy":"RER A / Transilien L","pontoise":"RER C / Transilien H",
    "saint-ouen-l-aumone":"RER C / Transilien H/L","osny":"RER C","eragny":"RER A",
    "garges-les-gonesse":"RER D","sarcelles":"RER D / Tramway T5",
    "villiers-le-bel":"RER D","gonesse":"RER B/D","goussainville":"RER D",
    "viarmes":"Transilien H","persan":"Transilien H","beaumont-sur-oise":"Transilien H",
    "chars":"Transilien J","pierrelaye":"Transilien H","saint-brice-sous-foret":"Transilien H",
    "soisy-sous-montmorency":"Transilien H","domont":"Transilien H",
    "roissy-en-france":"RER B (CDG)","louvres":"RER B","survilliers":"RER D",
    "fosses":"RER D","chambly":"Transilien H","bruyeres-sur-oise":"Transilien H",
    "bernes-sur-oise":"Transilien H","asnieres-sur-seine":"Transilien J / RER C",
    "colombes":"Transilien L/J","bois-colombes":"Transilien J",
    "la garenne-colombes":"Transilien J / RER A","gennevilliers":"Metro 13",
    "villeneuve-la-garenne":"Metro 13","clichy":"Metro 13",
    "courbevoie":"Transilien L / RER E","nanterre":"RER A / Transilien L/U",
    "levallois-perret":"Metro 3",
}


def norm(s):
    s = s.lower().strip()
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def get_station(city):
    cn = norm(city)
    for k, v in CITIES.items():
        kn = norm(k)
        if cn == kn or cn in kn or kn in cn:
            return v
    return None

def has_kw(text, kws):
    t = norm(text)
    return any(norm(k) in t for k in kws)

def fetch_page(url):
    h = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
    }
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
            raw = r.read()
            try: raw = gzip.decompress(raw)
            except: pass
            html = raw.decode("utf-8", errors="replace")
        i = html.find('id="__NEXT_DATA__"')
        if i == -1: return [], 0
        s = html.find(">", i) + 1
        e = html.find("</script>", s)
        d = json.loads(html[s:e]).get("props", {}).get("pageProps", {}).get("searchData", {})
        return d.get("ads", []), d.get("total", 0)
    except Exception as ex:
        print(f"  ERR fetch: {ex}")
        return [], 0

def parse(raw):
    fn = nf = None
    rooms = sq = ""
    for a in raw.get("attributes", []):
        k, v, vl = a.get("key",""), a.get("value",""), a.get("value_label","") or a.get("value","")
        if k == "floor_number":
            try: fn = int(v)
            except: pass
        elif k == "nb_floors_building":
            try: nf = int(v)
            except: pass
        elif k == "rooms": rooms = vl
        elif k == "square": sq = vl
    pl = raw.get("price", [])
    lid = raw.get("list_id")
    return {
        "id":  str(lid),
        "title": raw.get("subject", ""),
        "price": pl[0] if pl else None,
        "city": raw.get("location", {}).get("city", ""),
        "zip":  raw.get("location", {}).get("zipcode", ""),
        "sq": sq, "rooms": rooms, "fn": fn, "nf": nf,
        "url": f"https://www.leboncoin.fr/ad/ventes_immobilieres/{lid}",
    }

def search(loc, label):
    res = []; page = 1
    while True:
        ads, tot = fetch_page(
            f"https://www.leboncoin.fr/recherche?category=9&locations={loc}"
            f"&real_estate_type=2&price=0-110000&square=20-max&page={page}&kst=k"
        )
        if not ads: break
        for r in ads:
            a = parse(r)
            if not a["price"] or a["price"] > 110000: continue
            if has_kw(a["title"], VIAGER_KW) or has_kw(a["title"], LMNP_KW): continue
            if a["fn"] is None or a["nf"] is None or a["fn"] <= 0 or a["fn"] != a["nf"]: continue
            g = get_station(a["city"])
            if not g: continue
            a["gare"] = g
            res.append(a)
        if page * 35 >= tot or page >= 7: break
        page += 1
        time.sleep(1.5)
    print(f"  {label}: {len(res)} annonce(s)")
    return res

def tg(text):
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data=json.dumps({"chat_id": CHAT_ID, "parse_mode": "HTML",
                             "text": text, "disable_web_page_preview": True}).encode(),
            headers={"Content-Type": "application/json"}
        ), timeout=15)
    except Exception as e:
        print(f"  TG ERR: {e}")

def fmt(p):
    return f"{p:,}".replace(",", " ")

def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_seen(seen_dict):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_dict, f, ensure_ascii=False, indent=2)


def main():
    today = datetime.now().strftime("%d/%m/%Y")
    print(f"\n=== Agent Immo IDF - {today} ===\n")

    # Charger les annonces precedemment vues
    seen = load_seen()  # dict: id -> {title, price, city, zip, gare, url}
    print(f"  Annonces deja connues : {len(seen)}")

    # Lancer les recherches
    r95 = search("d_95", "LBC 95")
    r92 = search(
        "Asni%C3%A8res-sur-Seine_92600,Colombes_92700,Gennevilliers_92230,"
        "Villeneuve-la-Garenne_92390,Clichy_92110,Bois-Colombes_92270,"
        "La+Garenne-Colombes_92250,Courbevoie_92400,Nanterre_92000,Levallois-Perret_92300",
        "LBC Nord 92"
    )
    rb = search(
        "Conflans-Sainte-Honorine_78700,Sartrouville_78500,Houilles_78800,"
        "Ach%C3%A8res_78260,Maisons-Laffitte_78600,Persan_95340,"
        "Beaumont-sur-Oise_95260,Chambly_60230",
        "LBC Limitrophes 60/78"
    )

    # Dedupliquer
    dedup = {}
    for lst in [r95, r92, rb]:
        for a in lst:
            if a["id"] not in dedup:
                dedup[a["id"]] = a
    all_ads = sorted(dedup.values(), key=lambda x: x["price"])
    print(f"  Total unique : {len(all_ads)}")

    # Separer nouvelles / deja connues
    new_ads   = [a for a in all_ads if a["id"] not in seen]
    known_ads = [a for a in all_ads if a["id"] in seen]
    print(f"  Nouvelles : {len(new_ads)} | Deja connues : {len(known_ads)}")

    # ── MESSAGE 1 — Intro ──────────────────────────────────────────────────────
    tg(
        f"\U0001f3e0 <b>Recherche immo - {today}</b>\n"
        f"\U0001f4cd Val-d'Oise (95) + Nord 92 + Limitrophes 60/78\n"
        f"\U0001f4b0 Max 110 000 EUR | \U0001f4d0 Min 20m2\n"
        f"\U0001f3e2 Dernier etage | \U0001f6ab Sans viager/LMNP | \U0001f689 Proche gare"
    )
    time.sleep(1)

    # ── MESSAGE 2 — Annonces deja connues (UN SEUL message groupe) ────────────
    if known_ads:
        lines = [f"\U0001f4cb <b>Annonces deja connues ({len(known_ads)}) :</b>\n"]
        for a in known_ads:
            try:
                sq = int("".join(filter(str.isdigit, str(a["sq"])[:5])))
                stxt = f"{sq}m2 - {fmt(round(a['price']/sq))} EUR/m2"
            except: stxt = str(a["sq"])
            lines.append(
                f"\u2022 <a href=\"{a['url']}\">{a['title']}</a>\n"
                f"  \U0001f4b0 {fmt(a['price'])} EUR ({stxt}) | \U0001f4cd {a['city']} ({a['zip']}) | \U0001f689 {a['gare']}"
            )
        # Envoyer par blocs de 20 max (limite Telegram ~4096 chars)
        block = lines[0]
        for line in lines[1:]:
            candidate = block + "\n" + line
            if len(candidate) > 3800:
                tg(block)
                time.sleep(0.8)
                block = line
            else:
                block = candidate
        tg(block)
        time.sleep(1)

    # ── MESSAGES 3..N — Nouvelles annonces (un message par annonce) ───────────
    if new_ads:
        for a in new_ads:
            try:
                sq = int("".join(filter(str.isdigit, str(a["sq"])[:5])))
                stxt = f"{sq}m2 - {fmt(round(a['price']/sq))} EUR/m2"
            except: stxt = str(a["sq"])
            tg(
                f"\U0001f195 <b>{a['title']}</b>\n"
                f"\U0001f4b0 {fmt(a['price'])} EUR ({stxt})\n"
                f"\U0001f4d0 {a['rooms']} piece(s)\n"
                f"\U0001f4cd {a['city']} ({a['zip']})\n"
                f"\U0001f3e2 Dernier etage ({a['fn']}/{a['nf']})\n"
                f"\U0001f689 Gare proche : {a['gare']}\n"
                f"\U0001f517 <a href=\"{a['url']}\">Voir sur LeBonCoin</a>"
            )
            time.sleep(0.6)
    else:
        tg("\u2705 Aucune nouvelle annonce depuis la derniere verification.")

    # ── MESSAGE FINAL — Recap ─────────────────────────────────────────────────
    tg(
        f"\U0001f4ca <b>Recap - {today}</b>\n\n"
        f"LeBonCoin 95 : {len(r95)} annonce(s)\n"
        f"LeBonCoin Nord 92 : {len(r92)} annonce(s)\n"
        f"LeBonCoin Limitrophes 60/78 : {len(rb)} annonce(s)\n\n"
        f"<b>Total unique : {len(all_ads)} annonce(s)</b>\n"
        f"\U0001f195 Nouvelles : {len(new_ads)}\n"
        f"\U0001f4cb Deja connues : {len(known_ads)}"
    )

    # ── Sauvegarder les IDs vus ───────────────────────────────────────────────
    for a in all_ads:
        seen[a["id"]] = {
            "title": a["title"], "price": a["price"],
            "city": a["city"],   "zip":   a["zip"],
            "gare": a["gare"],   "url":   a["url"],
        }
    save_seen(seen)
    print(f"  seen_ids.json mis a jour : {len(seen)} entrees")
    print("=== Termine ===")


if __name__ == "__main__":
    main()
