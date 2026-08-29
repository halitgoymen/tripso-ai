import json
import os
import re
import sys
import pathlib
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL      = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
MODEL           = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
MAX_RETRY       = 3

GEOAPIFY_KEY = os.getenv("GEOAPIFY_KEY", "")
GEO_LIMIT    = 15

# ── Şehir adı normalizasyonu (Türkçe → Geoapify için İngilizce) ───────────────
_TR_MAP = str.maketrans("ışğüöçİŞĞÜÖÇ", "isguocISGUOC")

def _norm(s: str) -> str:
    return s.lower().translate(_TR_MAP)

TR_CITY_EN = {
    # Türkiye
    "istanbul": "Istanbul, Turkey",    "ankara": "Ankara, Turkey",
    "izmir": "Izmir, Turkey",          "antalya": "Antalya, Turkey",
    "bodrum": "Bodrum, Turkey",        "trabzon": "Trabzon, Turkey",
    "turkiye": "Istanbul, Turkey",     "turkey": "Istanbul, Turkey",
    # Mısır / Kuzey Afrika
    "misir": "Cairo, Egypt",           "kahire": "Cairo, Egypt",
    "cairo": "Cairo, Egypt",           "egypt": "Cairo, Egypt",
    "marakes": "Marrakech, Morocco",   "fas": "Casablanca, Morocco",
    "tunus": "Tunis, Tunisia",
    # Avrupa
    "roma": "Rome, Italy",             "italya": "Rome, Italy",
    "milano": "Milan, Italy",          "venedik": "Venice, Italy",
    "paris": "Paris, France",          "fransa": "Paris, France",
    "londra": "London, UK",            "ingiltere": "London, UK",
    "berlin": "Berlin, Germany",       "almanya": "Berlin, Germany",
    "munich": "Munich, Germany",       "munih": "Munich, Germany",
    "madrid": "Madrid, Spain",         "ispanya": "Madrid, Spain",
    "barselona": "Barcelona, Spain",   "barcelona": "Barcelona, Spain",
    "amsterdam": "Amsterdam, Netherlands",
    "hollanda": "Amsterdam, Netherlands",
    "brusej": "Brussels, Belgium",     "bruksel": "Brussels, Belgium",
    "zurih": "Zurich, Switzerland",    "isviçre": "Zurich, Switzerland",
    "viyana": "Vienna, Austria",       "avusturya": "Vienna, Austria",
    "prag": "Prague, Czech Republic",
    "budapeşte": "Budapest, Hungary",  "macaristan": "Budapest, Hungary",
    "varsova": "Warsaw, Poland",       "polonya": "Warsaw, Poland",
    "atina": "Athens, Greece",         "yunanistan": "Athens, Greece",
    "lizbon": "Lisbon, Portugal",      "portekiz": "Lisbon, Portugal",
    "kopenhag": "Copenhagen, Denmark",
    "stockholm": "Stockholm, Sweden",  "isveç": "Stockholm, Sweden",
    "oslo": "Oslo, Norway",            "norvec": "Oslo, Norway",
    "helsinki": "Helsinki, Finland",
    "bukres": "Bucharest, Romania",    "romanya": "Bucharest, Romania",
    "sofya": "Sofia, Bulgaria",        "bulgaristan": "Sofia, Bulgaria",
    "belgrad": "Belgrade, Serbia",     "sirbistan": "Belgrade, Serbia",
    "dubrovnik": "Dubrovnik, Croatia", "hırvatistan": "Zagreb, Croatia",
    # Orta Doğu
    "dubai": "Dubai, UAE",             "doha": "Doha, Qatar",
    "riyad": "Riyadh, Saudi Arabia",   "amman": "Amman, Jordan",
    "beyrut": "Beirut, Lebanon",
    # Asya
    "tokyo": "Tokyo, Japan",           "japonya": "Tokyo, Japan",
    "pekin": "Beijing, China",         "cin": "Beijing, China",
    "sangay": "Shanghai, China",       "hong kong": "Hong Kong",
    "seoul": "Seoul, South Korea",
    "bangkok": "Bangkok, Thailand",    "tayland": "Bangkok, Thailand",
    "singapur": "Singapore",           "singapore": "Singapore",
    "bali": "Bali, Indonesia",         "jakarta": "Jakarta, Indonesia",
    "kuala lumpur": "Kuala Lumpur, Malaysia",
    "delhi": "Delhi, India",           "mumbai": "Mumbai, India",
    "hindistan": "Delhi, India",
    # Amerika
    "new york": "New York, USA",       "los angeles": "Los Angeles, USA",
    "miami": "Miami, USA",             "chicago": "Chicago, USA",
    "san francisco": "San Francisco, USA",
    "toronto": "Toronto, Canada",      "vancouver": "Vancouver, Canada",
    # Okyanusya
    "sydney": "Sydney, Australia",     "avustralya": "Sydney, Australia",
    "melbourne": "Melbourne, Australia",
    # Arapça şehir adları (yaygın transkripsiyonlar)
    "kahirah": "Cairo, Egypt",         "al qahirah": "Cairo, Egypt",
    "dubayy": "Dubai, UAE",            "abu zabi": "Abu Dhabi, UAE",
    "bayrut": "Beirut, Lebanon",       "dimashq": "Damascus, Syria",
    "ar riyad": "Riyadh, Saudi Arabia",
    # Almanca
    "wien": "Vienna, Austria",         "munchen": "Munich, Germany",
    "koln": "Cologne, Germany",        "dusseldorf": "Dusseldorf, Germany",
    "prag": "Prague, Czech Republic",  "warschau": "Warsaw, Poland",
    "brussel": "Brussels, Belgium",    "genf": "Geneva, Switzerland",
    # Fransızca
    "vienne": "Vienna, Austria",       "varsovie": "Warsaw, Poland",
    "copenhague": "Copenhagen, Denmark",
    "lisbonne": "Lisbon, Portugal",    "la haye": "The Hague, Netherlands",
    # İspanyolca
    "atenas": "Athens, Greece",        "bruselas": "Brussels, Belgium",
    "viena": "Vienna, Austria",        "varsovia": "Warsaw, Poland",
    "lisboa": "Lisbon, Portugal",      "praga": "Prague, Czech Republic",
    # İtalyanca
    "londra_it": "London, UK",         "parigi": "Paris, France",
    "berlino": "Berlin, Germany",      "varsavia": "Warsaw, Poland",
}

def normalize_city_for_geo(raw: str) -> str:
    """Türkçe/yerel şehir adını Geoapify'ın anlayacağı İngilizce'ye çevirir."""
    if not raw:
        return raw
    normed = _norm(raw.strip())
    # Tam eşleşme
    if normed in TR_CITY_EN:
        return TR_CITY_EN[normed]
    # Dict key'lerini de normalize edip karşılaştır
    for key, en in TR_CITY_EN.items():
        if _norm(key) == normed:
            return en
    # Kısmi eşleşme
    for key, en in TR_CITY_EN.items():
        nk = _norm(key)
        if nk in normed or normed in nk:
            return en
    # Bilinmiyorsa olduğu gibi gönder (İngilizce şehirler için)
    return raw.strip()

MODE_VENUE = "venue"  # Sadece mekan tavsiyesi
MODE_PLAN  = "plan"   # Saatli tam gün planı

# ── Hedef JSON Formatları ─────────────────────────────────────────────────────
TARGET_VENUE_FORMAT = {
    "city": "string",
    "budget": "low",
    "venues": [
        {
            "name": "string",
            "category": "string",
            "estimated_cost": 0,
            "lat": 0.0,
            "lng": 0.0,
            "address": "string",
            "why": "Bu mekanı neden öneriyorsun (1 cümle)",
            "tip": "Pratik ipucu (1 cümle)"
        }
    ]
}

TARGET_PLAN_FORMAT = {
    "city": "string",
    "days": 3,
    "budget": "low",
    "plan": [
        {
            "day": 1,
            "schedule": [
                {
                    "time": "09:00",
                    "slot": "activity",
                    "name": "string",
                    "category": "string",
                    "estimated_cost": 0,
                    "lat": 0.0,
                    "lng": 0.0,
                    "address": "string",
                    "duration_min": 60
                }
            ]
        }
    ]
}

VALID_SLOTS    = {"breakfast", "activity", "lunch", "dinner", "evening"}
VALID_BUDGETS  = {"low", "mid", "high"}
VALID_TEMPOS   = {"relaxed", "moderate", "fast"}

REQUIRED_VENUE_ROOT  = ["city", "budget", "venues"]
REQUIRED_VENUE_ITEM  = ["name", "category", "estimated_cost", "lat", "lng", "address", "why", "tip"]
REQUIRED_PLAN_ROOT   = ["city", "days", "budget", "plan"]
REQUIRED_SCHED_ITEM  = ["time", "slot", "name", "category", "estimated_cost", "lat", "lng", "address", "duration_min"]

BUDGET_TIER_MAP = {
    "budget": "low", "economy": "low",
    "standard": "mid", "comfort": "mid",
    "premium": "high", "luxury": "high",
}

PACE_MAP = {
    "slow": "relaxed", "relaxed": "relaxed",
    "balanced": "moderate", "moderate": "moderate",
    "fast": "fast", "intensive": "fast",
}

PHYSICAL_MAP = {
    "low":    "Yürüyüş minimumda tutulsun, ulaşımı kolay ve yakın yerler seçilsin.",
    "medium": "Orta düzey yürüyüş kabul edilebilir (2-3 km/gün).",
    "high":   "Yoğun yürüyüş ve aktif rotalar uygundur.",
}

# Geoapify Places API category kodları
FOCUS_KINDS_MAP = {
    "culture":      "entertainment.museum,entertainment.culture",
    "food":         "catering.restaurant,catering.cafe",
    "nightlife":    "catering.bar,entertainment.nightclub",
    "nature":       "leisure.park,natural",
    "shopping":     "commercial.shopping_centre,commercial.marketplace",
    "art":          "entertainment.art_gallery,entertainment.museum",
    "history":      "tourism.sights,heritage",
    "architecture": "heritage,religion,tourism.sights",
    "_default":     "tourism.attraction,tourism.sights",
    "_food":        "catering.restaurant,catering.cafe",
}

TEMPO_RULES = {
    "relaxed": (
        "Tempo RELAXED: Günde en fazla 2-3 aktivite. "
        "Erken kalkış yok (09:30'da başla). Öğle molası uzun (90 dk). "
        "Akşam 19:00'da bitir."
    ),
    "moderate": (
        "Tempo MODERATE: Günde 3-4 aktivite. "
        "09:00'da başla. Öğle molası normal (60 dk). "
        "Akşam 20:00'da bitir."
    ),
    "fast": (
        "Tempo FAST: Günde 4-5 aktivite. "
        "08:00'da başla. Öğle molası kısa (45 dk). "
        "Akşam 21:00'a kadar devam edebilir."
    ),
}


# ── Geoapify Places API ───────────────────────────────────────────────────────
_geo_coords_cache: dict[str, tuple[float, float]] = {}

def _geo_city_coords(city: str) -> tuple[float, float] | None:
    en_city = normalize_city_for_geo(city)
    cache_key = en_city.lower()
    if cache_key in _geo_coords_cache:
        return _geo_coords_cache[cache_key]
    if en_city != city:
        print(f"  [GEO] '{city}' → '{en_city}' olarak aranıyor")
    try:
        r = requests.get(
            "https://api.geoapify.com/v1/geocode/search",
            params={"text": en_city, "limit": 1, "apiKey": GEOAPIFY_KEY},
            timeout=10,
        )
        if r.status_code != 200:
            print(f"  [GEO] Sehir bulunamadı ({en_city}): {r.status_code}")
            return None
        features = r.json().get("features", [])
        if not features:
            return None
        props  = features[0]["properties"]
        coords = (float(props["lat"]), float(props["lon"]))
        _geo_coords_cache[cache_key] = coords
        print(f"  [GEO] Koordinat: {coords[0]:.4f}, {coords[1]:.4f}")
        return coords
    except Exception as e:
        print(f"  [GEO] Koordinat hatası ({en_city}): {e}")
        return None


def _geo_search(categories: str, lat: float, lon: float) -> list[dict]:
    try:
        r = requests.get(
            "https://api.geoapify.com/v2/places",
            params={
                "categories": categories,
                "filter":     f"circle:{lon},{lat},10000",
                "limit":      GEO_LIMIT,
                "apiKey":     GEOAPIFY_KEY,
            },
            timeout=15,
        )
        if r.status_code != 200:
            print(f"  [GEO] {r.status_code} ({categories}): {r.text[:100]}")
            return []
        normalized = []
        for feat in r.json().get("features", []):
            props = feat.get("properties", {})
            name  = props.get("name") or props.get("address_line1", "")
            if not name:
                continue
            cats     = props.get("categories", [])
            cat_name = cats[0].replace(".", " ").title() if cats else "Place"
            normalized.append({
                "fsq_id":     props.get("place_id", ""),
                "name":       name,
                "categories": [{"name": cat_name}],
                "geocodes":   {"main": {
                    "latitude":  props.get("lat", 0.0),
                    "longitude": props.get("lon", 0.0),
                }},
                "location":   {"formatted_address": props.get("formatted", "")},
                "price":      0,
            })
        return normalized
    except Exception as e:
        print(f"  [GEO] Arama hatası ({categories}): {e}")
        return []


def fetch_places(city: str, focus: list, must_see: str, interests: list, mode: str) -> list[dict]:
    # Geoapify çağrısı kaldırıldı — Qwen kendi bilgisiyle planlıyor
    return []


def format_places_for_prompt(places: list[dict]) -> str:
    if not places:
        return ""
    lines = []
    for i, p in enumerate(places, 1):
        name = p.get("name", "?")
        cats = p.get("categories", [])
        cat  = cats[0]["name"] if cats else "Place"
        geo  = p.get("geocodes", {}).get("main", {})
        lat  = geo.get("latitude", 0.0)
        lng  = geo.get("longitude", 0.0)
        loc  = p.get("location", {})
        addr = loc.get("formatted_address") or loc.get("address", "")
        lines.append(f"{i}. {name} | {cat} | lat:{lat} lng:{lng} | {addr}")
    return "\n".join(lines)


# ── Trip Request Parser ────────────────────────────────────────────────────────
def parse_trip_request(raw: dict) -> dict:
    city = raw.get("destinationCity") or raw.get("city", "")

    days = raw.get("days")
    if not days:
        start = raw.get("startDate", "")
        end   = raw.get("endDate", "")
        if start and end:
            fmt   = "%Y-%m-%dT%H:%M:%S.%fZ"
            delta = datetime.strptime(end, fmt) - datetime.strptime(start, fmt)
            days  = max(delta.days, 1)
        else:
            days = 2

    budget_raw = (raw.get("budgetTier") or raw.get("budget", "mid")).lower()
    budget = BUDGET_TIER_MAP.get(budget_raw, "mid")

    profile  = raw.get("profileSnapshot") or {}
    pace_raw = (profile.get("pace") or raw.get("tempo", "balanced")).lower()
    tempo    = PACE_MAP.get(pace_raw, "moderate")

    specific     = raw.get("tripSpecificInterests") or []
    travel_focus = raw.get("travelFocus") or []
    must_see     = ", ".join(specific) if specific else ""

    travelers = raw.get("travelers") or {}
    adults    = travelers.get("adults", 1)
    children  = travelers.get("children", 0)

    return {
        "city":               city,
        "days":               int(days),
        "budget":             budget,
        "must_see":           must_see,
        "tempo":              tempo,
        "travel_focus":       travel_focus,
        "dietary":            profile.get("dietary") or [],
        "alcohol":            profile.get("alcohol", "yes"),
        "physical":           profile.get("physicalCapability", "medium").lower(),
        "transport_style":    profile.get("transportationStyle", "any"),
        "profile_interests":  profile.get("interests") or [],
        "travel_experience":  profile.get("travelExperience", ""),
        "accommodation_tier": profile.get("accommodationTier", ""),
        "adults":             adults,
        "children":           children,
        "budget_amount":      raw.get("budgetAmount", ""),
        "budget_currency":    raw.get("budgetCurrency", "EUR"),
        "occasion":           raw.get("occasion", ""),
        "free_notes":         raw.get("freeTextNotes", ""),
        "day_start":          raw.get("dayStart", "09:00"),
        "day_end":            raw.get("dayEnd", "22:00"),
    }


# ── CLI Arayüzü ───────────────────────────────────────────────────────────────
def ask(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    val  = input(f"  {label}{hint}: ").strip()
    return val if val else default


def ask_choice(label: str, choices: set, default: str) -> str:
    opts = " / ".join(sorted(choices))
    while True:
        val = ask(f"{label} ({opts})", default)
        if val in choices:
            return val
        print(f"  ⚠️  Geçerli seçenekler: {opts}")


def ask_days() -> int:
    while True:
        val = ask("Days (gün sayısı)", "2")
        if val.isdigit() and int(val) > 0:
            return int(val)
        print("  ⚠️  Pozitif bir tam sayı girin.")


def ask_time_range() -> tuple[str, str]:
    """Günün başlangıç ve bitiş saatini sorar. HH:MM formatı beklenir."""
    time_re = re.compile(r"^\d{1,2}:\d{2}$")

    while True:
        start = ask("Günün başlangıç saati (HH:MM)", "09:00")
        if time_re.match(start):
            break
        print("  ⚠️  Format: HH:MM  (örn. 09:00 veya 17:30)")

    while True:
        end = ask("Günün bitiş saati   (HH:MM)", "22:00")
        if time_re.match(end):
            # gece yarısı geçişine izin ver (00:00 veya 23:59 gibi)
            if end <= start and end not in ("00:00", "23:59"):
                print("  ⚠️  Bitiş saati başlangıçtan sonra olmalı (ya da 00:00 kullan).")
                continue
            break
        print("  ⚠️  Format: HH:MM  (örn. 22:00 veya 00:00)")

    return start, end


def ask_mode() -> str:
    print()
    print("=" * 52)
    print("         AI Travel Planner — Seyahat Asistanı")
    print("=" * 52)
    print()
    print("  Ne yapmak istersiniz?")
    print()
    print("  [1] Mekan tavsiyesi  — Şehir için en iyi mekanları listele")
    print("  [2] Günlük plan      — Kahvaltı, aktivite, yemek dahil saatli plan")
    print()
    while True:
        choice = input("  Seçiminiz (1/2): ").strip()
        if choice == "1":
            return MODE_VENUE
        if choice == "2":
            return MODE_PLAN
        print("  ⚠️  1 veya 2 girin.")


def get_user_input(mode: str) -> dict:
    print()
    print("  (Boş bırakırsanız varsayılan kullanılır)\n")

    city          = ask("City (şehir)", "Paris")
    budget        = ask_choice("Budget", VALID_BUDGETS, "mid")
    budget_amount = ask("Toplam bütçe miktarı (opsiyonel)", "")
    budget_currency = ask("Para birimi", "EUR") if budget_amount else "EUR"
    must_see      = ask("Must see (virgülle ayırın)", "")
    focus_input   = ask("Travel focus (culture, food, nightlife, nature...)", "")
    travel_focus  = [f.strip() for f in focus_input.split(",") if f.strip()]
    dietary_input = ask("Diyet kısıtları (vegetarian, gluten-free...)", "")
    dietary       = [d.strip() for d in dietary_input.split(",") if d.strip()]
    alcohol       = ask_choice("Alkol", {"yes", "no"}, "yes")
    physical      = ask_choice("Fiziksel kapasite", {"low", "medium", "high"}, "medium")
    transport     = ask_choice("Ulaşım tercihi", {"public", "taxi", "any"}, "any")
    occasion      = ask("Özel durum (anniversary, birthday...)", "")
    adults        = ask("Yetişkin sayısı", "1")
    children      = ask("Çocuk sayısı", "0")
    notes         = ask("Ek not", "")

    params = {
        "city":               city,
        "budget":             budget,
        "must_see":           must_see,
        "travel_focus":       travel_focus,
        "dietary":            dietary,
        "alcohol":            alcohol,
        "physical":           physical,
        "transport_style":    transport,
        "profile_interests":  [],
        "travel_experience":  "",
        "accommodation_tier": "",
        "adults":             int(adults) if adults.isdigit() else 1,
        "children":           int(children) if children.isdigit() else 0,
        "budget_amount":      budget_amount,
        "budget_currency":    budget_currency,
        "occasion":           occasion,
        "free_notes":         notes,
    }

    if mode == MODE_PLAN:
        params["days"]  = ask_days()
        params["tempo"] = ask_choice("Tempo", VALID_TEMPOS, "moderate")
        start_t, end_t  = ask_time_range()
        params["day_start"] = start_t
        params["day_end"]   = end_t
    else:
        params["days"]      = 1
        params["tempo"]     = "moderate"
        params["day_start"] = "09:00"
        params["day_end"]   = "22:00"

    return params


# ── Prompt Builder'lar ────────────────────────────────────────────────────────
def _profile_rules(p: dict) -> str:
    rules = []
    if p.get("dietary"):
        rules.append(f"- Diyet kısıtı: {', '.join(p['dietary'])}. Yemek önerilerinde bu kısıtlamalara uyan mekanları seç.")
    if p.get("alcohol") == "no":
        rules.append("- Kullanıcı alkol kullanmıyor. Bar ve alkol odaklı mekanları önerme.")
    physical_note = PHYSICAL_MAP.get(p.get("physical", "medium"), "")
    if physical_note:
        rules.append(f"- Fiziksel kapasite: {physical_note}")
    if p.get("transport_style") == "public":
        rules.append("- Ulaşım: toplu taşıma. Metro/otobüs erişimi olan yerleri tercih et.")
    if p.get("occasion"):
        rules.append(f"- Özel durum: {p['occasion']}. Romantik veya özel atmosferli mekanları ön plana çıkar.")
    if p.get("travel_experience") == "experienced":
        rules.append("- Deneyimli gezgin. Turistik klişelerle sınırlı kalma, özgün yerler de ekle.")
    if p.get("adults", 1) >= 2 and not p.get("children"):
        rules.append(f"- {p['adults']} yetişkin, çocuk yok. Yetişkin odaklı aktiviteler uygundur.")
    return "\n".join(rules)


def build_user_prompt(p: dict, mode: str) -> str:
    city_raw = p['city']
    city_en  = normalize_city_for_geo(city_raw)
    city_str = city_en if city_en != city_raw else city_raw
    lines = [f"City: {city_str}", f"Budget: {p['budget']}"]

    if p.get("budget_amount"):
        lines.append(f"Total Budget: {p['budget_amount']} {p['budget_currency']}")

    traveler_str = f"{p['adults']} adult(s)"
    if p.get("children"):
        traveler_str += f", {p['children']} child(ren)"
    lines.append(f"Travelers: {traveler_str}")

    if p.get("must_see"):
        lines.append(f"Must see: {p['must_see']}")
    if p.get("travel_focus"):
        lines.append(f"Travel focus: {', '.join(p['travel_focus'])}")
    if p.get("profile_interests"):
        lines.append(f"Interests: {', '.join(p['profile_interests'])}")

    if mode == MODE_PLAN:
        lines.append(f"Days: {p['days']}")
        lines.append(f"Tempo: {p['tempo']}")
        lines.append(f"Day hours: {p.get('day_start', '09:00')} — {p.get('day_end', '22:00')}")

    if p.get("dietary"):
        lines.append(f"Dietary restrictions: {', '.join(p['dietary'])}")
    lines.append(f"Alcohol: {p['alcohol']}")
    lines.append(f"Physical capability: {p['physical']}")
    lines.append(f"Transportation: {p['transport_style']}")
    if p.get("occasion"):
        lines.append(f"Occasion: {p['occasion']}")
    if p.get("travel_experience"):
        lines.append(f"Travel experience: {p['travel_experience']}")
    if p.get("free_notes"):
        lines.append(f"Notes: {p['free_notes']}")

    return "\n".join(lines)


def build_system_prompt_venue(p: dict, fsq_context: str) -> str:
    city_en      = normalize_city_for_geo(p.get("city", ""))
    budget_n     = p.get("budget", "mid")
    must         = p.get("must_see", "")
    notes        = (p.get("free_notes") or "").strip()
    profile_bits = _profile_rules(p)

    focus      = p.get("travel_focus", [])
    focus_map  = {
        "history": "historical sites", "culture": "cultural venues",
        "nature": "parks and outdoor", "beach": "beaches/swimming",
        "food": "restaurants/cafes", "nightlife": "bars/clubs",
        "shopping": "markets/shops", "art": "galleries",
        "architecture": "architectural landmarks", "adventure": "active spots",
        "wellness": "spa/wellness",
    }
    focus_str = ", ".join(focus_map[f] for f in focus if f in focus_map)

    notes_section = f"\nUSER INSTRUCTIONS (MUST FOLLOW EXACTLY): {notes}" if notes else ""
    must_str      = f"\nMust-see: {must}" if must else ""
    focus_section = f"\nFocus on: {focus_str}" if focus_str else ""
    extra         = f"\nProfile: {profile_bits}" if profile_bits else ""
    place_note    = (f"\nPlaces:\n{fsq_context}" if fsq_context
                     else f"\nUse only real, well-known places in {city_en}. No invented places.")

    json_fmt = (
        '{"city":"str","budget":"' + budget_n + '","venues":['
        '{"name":"str","category":"str","estimated_cost":0,"lat":0.0,"lng":0.0,'
        '"address":"str","why":"1 sentence Turkish","tip":"1 sentence Turkish"}]}'
    )
    return (
        f"You are a travel planner. Output ONLY valid JSON, no markdown, no explanation.{notes_section}\n"
        f"City: {city_en} | Budget: {budget_n}{must_str}{focus_section}{place_note}{extra}\n\n"
        f"JSON format:\n{json_fmt}\n\n"
        f"Rules: 5-12 venues, estimated_cost integer, lat/lng real coords or 0.0, "
        f"why/tip in Turkish. OUTPUT: JSON only."
    )


def build_system_prompt_plan(p: dict, fsq_context: str) -> str:
    city_en   = normalize_city_for_geo(p.get("city", ""))
    day_start = p.get("day_start", "09:00")
    day_end   = p.get("day_end", "22:00")
    tempo     = p.get("tempo", "moderate")
    days      = p.get("days", 2)
    budget_n  = p.get("budget", "mid")
    notes     = (p.get("free_notes") or "").strip()

    # Nottan saat override çıkar (ASCII normalize üzerinde çalış)
    import re as _re
    def _extract_time(pattern, text):
        m = _re.search(pattern, text, _re.IGNORECASE)
        if not m: return None
        h = int(m.group(1)); mn = m.group(2) or "00"
        return f"{h:02d}:{mn}" if 0 <= h <= 23 else None

    _nn = _norm(notes)  # Türkçe karakterleri ASCII'ye çevir
    # gece 12 / gece yarısı → 00:00
    _nn = _re.sub(r"gece\s*12\b|gece\s*yarisi|midnight", "00:00", _nn, _re.IGNORECASE)
    _nn = _re.sub(r"ogle[n]?\s*12\b|noon", "12:00", _nn, _re.IGNORECASE)

    # Başlangıç: sayıdan sonra "de/da" sonra başla/başlat/start
    t = _extract_time(r"(\d{1,2})(?::(\d{2}))?\s*(?:'?de|'?da)?\s*(?:basla|start)", _nn)
    if t: day_start = t
    # Bitiş: sayıdan sonra "de/da" sonra bit/end/finish/kadar
    t = _extract_time(r"(\d{1,2})(?::(\d{2}))?\s*(?:'?de|'?da)?\s*(?:bit|end|finish|kadar)", _nn)
    if t: day_end = t

    start_h = int(day_start.split(":")[0])
    end_h   = int(day_end.split(":")[0]) if day_end != "00:00" else 24
    total_h = (end_h - start_h) if end_h > start_h else (24 - start_h + end_h)

    if start_h >= 12:
        meal_hint = "Day starts at noon — begin with lunch (no breakfast)."
    elif start_h >= 10:
        meal_hint = "Late start — begin with activity or lunch (no breakfast)."
    else:
        meal_hint = "Early start — begin with breakfast."

    if end_h >= 22 or day_end == "00:00":
        end_hint = (f"Day ends at {day_end} — MUST include dinner (~19:00-20:00) "
                    f"and an evening activity after dinner. Fill the day until {day_end}.")
    elif end_h >= 20:
        end_hint = f"Day ends at {day_end} — include dinner. Fill the day until {day_end}."
    else:
        end_hint = f"Day ends at {day_end} — no dinner or evening slots needed."

    # Gün uzunluğuna göre aktivite sayısı (ortalama 90 dk/aktivite)
    suggested = max(3, min(8, round(total_h / 1.5)))
    pace_adj  = {"relaxed": -1, "moderate": 0, "fast": 1}.get(tempo, 0)
    target    = max(3, suggested + pace_adj)
    tempo_str = f"~{target} scheduled items (activities + meals) to fill {total_h} hours"

    focus      = p.get("travel_focus", [])
    focus_map  = {
        "history":      "prioritize historical sites, ruins, monuments",
        "culture":      "prioritize cultural venues, museums",
        "nature":       "prioritize parks, gardens, outdoor spots",
        "beach":        "include beach or swimming spots",
        "food":         "include local restaurants and cafes",
        "nightlife":    "include bars, clubs or night shows",
        "shopping":     "include markets and shopping areas",
        "art":          "include galleries and art venues",
        "architecture": "include architectural landmarks",
        "adventure":    "include active/adventure activities",
        "wellness":     "include spa or wellness experiences",
    }
    focus_hints = "; ".join(focus_map[f] for f in focus if f in focus_map)

    profile_bits = _profile_rules(p)
    extra        = f"\nProfile: {profile_bits}" if profile_bits else ""
    place_note   = (f"\nAvailable places:\n{fsq_context}" if fsq_context
                    else f"\nUse only real, well-known places in {city_en}. No invented places.")

    # Kullanıcı notu en üste, zorunlu kural olarak
    notes_section = f"\nUSER INSTRUCTIONS (MUST FOLLOW EXACTLY): {notes}" if notes else ""

    json_fmt = (
        '{"city":"str","days":' + str(days) + ',"budget":"' + budget_n + '",'
        '"plan":[{"day":1,"schedule":['
        '{"time":"HH:MM","slot":"activity|breakfast|lunch|dinner|evening",'
        '"name":"str","category":"str","estimated_cost":0,"lat":0.0,"lng":0.0,'
        '"address":"str","duration_min":60}]}]}'
    )

    return (
        f"You are a travel planner. Output ONLY valid JSON, no markdown, no explanation.{notes_section}\n\n"
        f"Destination: {city_en} | {days} days | Budget: {budget_n}\n"
        f"STRICT TIME RULE: Day runs {day_start} to {day_end} ({total_h} hours). "
        f"First item MUST start at {day_start}. Last item must finish by {day_end}. "
        f"Do NOT stop scheduling early — fill ALL {total_h} hours. Target: {tempo_str}.\n"
        f"{meal_hint} {end_hint}\n"
        + (f"Focus: {focus_hints}\n" if focus_hints else "")
        + f"{place_note}{extra}\n\n"
        f"JSON format:\n{json_fmt}\n\n"
        f"slot: activity / breakfast / lunch / dinner / evening\n"
        f"estimated_cost: integer EUR. lat/lng: real coords or 0.0. OUTPUT: JSON only."
    )


# ── Ollama API ────────────────────────────────────────────────────────────────
def call_qwen(user_prompt: str, system_prompt: str) -> str:
    payload = {
        "model":  MODEL,
        "prompt": f"{system_prompt}\n\nRequest:\n{user_prompt}",
        "stream": False,
        "options": {
            "temperature": 0.1,   # daha deterministik = daha az sapma
            "num_predict": 4096,  # çoğu plan için yeterli
            "top_p":       0.9,
            "repeat_penalty": 1.1,
        },
    }
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=240)
        r.raise_for_status()
        return r.json().get("response", "")
    except requests.exceptions.ConnectionError:
        print("  [Ollama] Baglanti yok — 'ollama serve' calisıyor mu?")
        return ""
    except Exception as e:
        print(f"  [Ollama] Hata: {e}")
        return ""


def _try_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def clean_and_parse(text: str) -> dict | None:
    if not text:
        return None

    # 1. Markdown temizle
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # 2. Direkt parse
    result = _try_json(text)
    if result is not None:
        return result

    # 3. İlk { / son } arasını al
    start = text.find("{")
    end   = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        print(f"  [parse] JSON bloğu bulunamadı. Çıktı başı: {text[:120]!r}")
        return None

    snippet = text[start:end + 1]

    # 4. Ham parse
    result = _try_json(snippet)
    if result is not None:
        return result

    # 5. Trailing comma temizle
    fixed = re.sub(r",\s*([}\]])", r"\1", snippet)
    result = _try_json(fixed)
    if result is not None:
        return result

    # 6. Tek tırnak → çift tırnak (Qwen bazen yapar)
    fixed2 = re.sub(r"(?<![\\])'", '"', fixed)
    result = _try_json(fixed2)
    if result is not None:
        return result

    print(f"  [parse] Tüm stratejiler başarısız. Snippet başı: {snippet[:150]!r}")
    return None


# ── Validation ────────────────────────────────────────────────────────────────
def validate_venue_json(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Kök eleman dict değil."
    for f in REQUIRED_VENUE_ROOT:
        if f not in data:
            return False, f"Eksik alan: '{f}'"
    if data["budget"] not in VALID_BUDGETS:
        return False, f"'budget' geçersiz: {data['budget']}"
    if not isinstance(data["venues"], list) or len(data["venues"]) == 0:
        return False, "'venues' dolu liste olmalı."
    for i, v in enumerate(data["venues"]):
        for vf in REQUIRED_VENUE_ITEM:
            if vf not in v:
                return False, f"venues[{i}] içinde '{vf}' eksik."
        for num_field in ("estimated_cost", "lat", "lng"):
            if not isinstance(v.get(num_field), (int, float)):
                try:
                    v[num_field] = float(v[num_field])
                except Exception:
                    v[num_field] = 0
    return True, "OK"


def validate_plan_json(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "Kök eleman dict değil."
    for f in REQUIRED_PLAN_ROOT:
        if f not in data:
            return False, f"Eksik alan: '{f}'"
    # budget string değilse geç, Qwen bazen yanlış tip yazar
    if isinstance(data["budget"], str) and data["budget"] not in VALID_BUDGETS:
        data["budget"] = "mid"   # sessizce düzelt
    if not isinstance(data["days"], int):
        try:
            data["days"] = int(data["days"])
        except Exception:
            return False, "'days' integer olmalı."
    if not isinstance(data["plan"], list) or len(data["plan"]) == 0:
        return False, "'plan' dolu liste olmalı."
    for i, day_item in enumerate(data["plan"]):
        if "day" not in day_item:
            return False, f"plan[{i}] içinde 'day' yok."
        schedule = day_item.get("schedule", [])
        if not schedule:
            return False, f"plan[{i}] içinde 'schedule' dolu olmalı."
        slots_in_day = [s.get("slot") for s in schedule]
        # Sadece en az 1 activity zorunlu; breakfast/lunch opsiyonel
        if "activity" not in slots_in_day:
            return False, f"plan[{i}] içinde en az 1 'activity' slotu yok."
        for j, item in enumerate(schedule):
            for sf in REQUIRED_SCHED_ITEM:
                if sf not in item:
                    return False, f"plan[{i}].schedule[{j}] içinde '{sf}' eksik."
            # Geçersiz slot adını sessizce düzelt
            if item.get("slot") not in VALID_SLOTS:
                item["slot"] = "activity"
            # Sayısal alanları sessizce düzelt
            for num_field in ("estimated_cost", "lat", "lng", "duration_min"):
                if not isinstance(item.get(num_field), (int, float)):
                    try:
                        item[num_field] = float(item[num_field])
                    except Exception:
                        item[num_field] = 0
    return True, "OK"


# ── Çıktı ─────────────────────────────────────────────────────────────────────
SLOT_EMOJI = {
    "breakfast": "☕",
    "activity":  "🏛 ",
    "lunch":     "🍽 ",
    "dinner":    "🍷",
    "evening":   "🌙",
}

SLOT_TR = {
    "breakfast": "Kahvaltı",
    "activity":  "Aktivite",
    "lunch":     "Öğle Yemeği",
    "dinner":    "Akşam Yemeği",
    "evening":   "Akşam",
}


def print_venue_list(data: dict) -> None:
    print()
    print("=" * 58)
    print(f"  {data['city'].upper()} — MEKAN TAVSİYELERİ — {data['budget'].upper()} BÜTÇE")
    print("=" * 58)
    for i, v in enumerate(data["venues"], 1):
        cost_str = "Ücretsiz" if v["estimated_cost"] == 0 else f"~{v['estimated_cost']} EUR"
        lat, lng = v.get("lat", 0), v.get("lng", 0)
        print(f"\n  {i}. {v['name']}  [{v['category']}]  {cost_str}")
        if lat and lng:
            print(f"     📍 {lat}, {lng}  |  {v.get('address', '')}")
        print(f"     ✔  {v.get('why', '')}")
        if v.get("tip"):
            print(f"     💡 {v['tip']}")
    print("=" * 58)


def print_plan(data: dict) -> None:
    print()
    print("=" * 58)
    print(f"  {data['city'].upper()} — {data['days']} GÜN — {data['budget'].upper()} BÜTÇE")
    print("=" * 58)
    for day_item in data["plan"]:
        print(f"\n  ── Gün {day_item['day']} ──────────────────────────────────")
        for item in day_item.get("schedule", []):
            slot     = item.get("slot", "activity")
            emoji    = SLOT_EMOJI.get(slot, "📌")
            slot_tr  = SLOT_TR.get(slot, slot)
            cost     = item["estimated_cost"]
            cost_str = "Ücretsiz" if cost == 0 else f"~{cost} EUR"
            dur      = item.get("duration_min", 0)
            lat, lng = item.get("lat", 0), item.get("lng", 0)
            addr     = item.get("address", "")
            print(f"\n  {item['time']}  {emoji} [{slot_tr}]  {item['name']}")
            print(f"           {item['category']}  |  {cost_str}  |  ~{dur} dk")
            if lat and lng:
                print(f"           📍 {lat}, {lng}  |  {addr}")
    total = data.get("estimated_total_cost")
    if total:
        print(f"\n  Tahmini Toplam: ~{total} EUR")
    print("=" * 58)


def print_parsed_params(p: dict, mode: str) -> None:
    mode_label = "Mekan Tavsiyesi" if mode == MODE_VENUE else "Günlük Plan"
    print()
    print("=" * 52)
    print(f"         AI Travel Planner — {mode_label}")
    print("=" * 52)
    print(f"  Şehir        : {p['city']}")
    if mode == MODE_PLAN:
        print(f"  Gün          : {p['days']}")
    bstr = p["budget"] + (f"  ({p['budget_amount']} {p['budget_currency']})" if p.get("budget_amount") else "")
    print(f"  Bütçe        : {bstr}")
    print(f"  Kişi         : {p['adults']} yetişkin" + (f", {p['children']} çocuk" if p.get("children") else ""))
    print(f"  Must-see     : {p['must_see'] or '—'}")
    print(f"  Odak         : {', '.join(p['travel_focus']) or '—'}")
    if mode == MODE_PLAN:
        print(f"  Tempo        : {p['tempo']}")
        print(f"  Saat aralığı : {p.get('day_start', '09:00')} — {p.get('day_end', '22:00')}")
    print(f"  Diyet        : {', '.join(p['dietary']) if p['dietary'] else '—'}")
    print(f"  Alkol        : {p['alcohol']}")
    print(f"  Fiziksel     : {p['physical']}")
    print(f"  Ulaşım       : {p['transport_style']}")
    print(f"  Özel durum   : {p['occasion'] or '—'}")
    print(f"  Not          : {p['free_notes'] or '—'}")


# ── Ana Akış ──────────────────────────────────────────────────────────────────
def main() -> None:
    # Mod seçimi (her zaman sorulur)
    mode = ask_mode()

    # Parametre toplama
    if len(sys.argv) > 1:
        json_path = pathlib.Path(sys.argv[1])
        if not json_path.exists():
            print(f"🚨 Dosya bulunamadı: {json_path}")
            sys.exit(1)
        with json_path.open(encoding="utf-8") as f:
            raw = json.load(f)
        params = parse_trip_request(raw)
        print_parsed_params(params, mode)
    else:
        params = get_user_input(mode)

    # Foursquare'den gerçek mekanları çek
    fsq_places  = fetch_places(
        city      = params["city"],
        focus     = params["travel_focus"],
        must_see  = params["must_see"],
        interests = params["profile_interests"],
        mode      = mode,
    )
    fsq_context = format_places_for_prompt(fsq_places)

    user_prompt = build_user_prompt(params, mode)

    if mode == MODE_VENUE:
        system_prompt = build_system_prompt_venue(params, fsq_context)
        validate_fn   = validate_venue_json
        print_fn      = print_venue_list
    else:
        system_prompt = build_system_prompt_plan(params, fsq_context)
        validate_fn   = validate_plan_json
        print_fn      = print_plan

    print(f"\n  🤖 {'Mekanlar' if mode == MODE_VENUE else 'Plan'} oluşturuluyor ({MAX_RETRY} deneme hakkı)...")

    final_data = None
    for attempt in range(1, MAX_RETRY + 1):
        print(f"  Deneme {attempt}/{MAX_RETRY}...", end=" ", flush=True)
        raw_resp = call_qwen(user_prompt, system_prompt)
        data     = clean_and_parse(raw_resp)

        if data is None:
            print("❌ JSON parse edilemedi.")
            continue

        ok, msg = validate_fn(data)
        if ok:
            final_data = data
            print("✅")
            break
        print(f"❌ {msg}")

    if final_data:
        print_fn(final_data)
    else:
        print(f"\n  🚨 {MAX_RETRY} deneme sonunda geçerli çıktı üretilemedi.")


if __name__ == "__main__":
    main()
