#!/usr/bin/env python3
"""
Tripso Dev Server  —  http://localhost:8080
  /            → Web dashboard (tripso_web.html)
  /api/plan    → Foursquare + Qwen AI seyahat planı
  /api/flights → Travelpayouts uçuş arama + Qwen analizi
"""

import os, sys, json, time
import requests as http
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ── qwen_test.py'den import ───────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from qwen_test import (
    fetch_places, format_places_for_prompt,
    build_user_prompt, build_system_prompt_venue, build_system_prompt_plan,
    call_qwen, clean_and_parse, validate_venue_json, validate_plan_json,
    parse_trip_request, MODE_VENUE, MODE_PLAN, MAX_RETRY,
)

# ── Config ────────────────────────────────────────────────────────────────────
TRAVELPAYOUTS_TOKEN = os.getenv("TRAVELPAYOUTS_TOKEN", "")
TP_BASE             = "https://api.travelpayouts.com"
PORT                = int(os.getenv("SERVER_PORT", "8080"))

# City / Country → IATA sözlüğü (Türkçe + İngilizce)
CITY_IATA = {
    # Türkiye şehirleri
    "istanbul": "IST", "ankara": "ESB", "izmir": "ADB", "antalya": "AYT",
    "bodrum": "BJV", "dalaman": "DLM", "trabzon": "TZX", "adana": "ADA",
    "gaziantep": "GZT", "kayseri": "ASR", "samsun": "SZF", "erzurum": "ERZ",
    "türkiye": "IST", "turkey": "IST",
    # İtalya
    "roma": "FCO", "rome": "FCO", "milano": "MXP", "milan": "MXP",
    "venedik": "VCE", "venice": "VCE", "floransa": "FLR", "florence": "FLR",
    "napoli": "NAP", "naples": "NAP", "italya": "FCO", "italy": "FCO",
    # Fransa
    "paris": "CDG", "nice": "NCE", "lyon": "LYS",
    "marsilya": "MRS", "marseille": "MRS", "fransa": "CDG", "france": "CDG",
    # İngiltere
    "londra": "LHR", "london": "LHR", "manchester": "MAN",
    "ingiltere": "LHR", "uk": "LHR",
    # Almanya
    "berlin": "BER", "münih": "MUC", "munich": "MUC",
    "frankfurt": "FRA", "hamburg": "HAM", "düsseldorf": "DUS",
    "almanya": "FRA", "germany": "FRA",
    # İspanya
    "madrid": "MAD", "barcelona": "BCN", "sevilla": "SVQ", "seville": "SVQ",
    "valensiya": "VLC", "valencia": "VLC", "palma": "PMI", "ibiza": "IBZ",
    "ispanya": "MAD", "spain": "MAD",
    # Hollanda / Belçika / İsviçre
    "amsterdam": "AMS", "hollanda": "AMS", "netherlands": "AMS",
    "brüksel": "BRU", "brussels": "BRU", "belçika": "BRU", "belgium": "BRU",
    "zürih": "ZRH", "zurich": "ZRH", "cenevre": "GVA", "geneva": "GVA",
    "isviçre": "ZRH", "switzerland": "ZRH",
    # Avusturya / Çekya / Macaristan / Polonya
    "viyana": "VIE", "vienna": "VIE", "avusturya": "VIE", "austria": "VIE",
    "prag": "PRG", "prague": "PRG", "çek cumhuriyeti": "PRG", "czechia": "PRG",
    "budapeşte": "BUD", "budapest": "BUD", "macaristan": "BUD", "hungary": "BUD",
    "varşova": "WAW", "warsaw": "WAW", "polonya": "WAW", "poland": "WAW",
    # Yunanistan / Portekiz
    "atina": "ATH", "athens": "ATH", "yunanistan": "ATH", "greece": "ATH",
    "lizbon": "LIS", "lisbon": "LIS", "porto": "OPO",
    "portekiz": "LIS", "portugal": "LIS",
    # İskandinavya
    "kopenhag": "CPH", "copenhagen": "CPH", "danimarka": "CPH", "denmark": "CPH",
    "stockholm": "ARN", "isveç": "ARN", "sweden": "ARN",
    "oslo": "OSL", "norveç": "OSL", "norway": "OSL",
    "helsinki": "HEL", "finlandiya": "HEL", "finland": "HEL",
    # Doğu Avrupa
    "bükreş": "OTP", "bucharest": "OTP", "romanya": "OTP", "romania": "OTP",
    "sofya": "SOF", "sofia": "SOF", "bulgaristan": "SOF", "bulgaria": "SOF",
    "belgrad": "BEG", "belgrade": "BEG", "sırbistan": "BEG", "serbia": "BEG",
    "zagreb": "ZAG", "hırvatistan": "ZAG", "croatia": "ZAG",
    "dubrovnik": "DBV", "split": "SPU",
    "köln": "CGN", "cologne": "CGN",
    # Orta Doğu / Körfez
    "dubai": "DXB", "abu dhabi": "AUH", "doha": "DOH",
    "riyad": "RUH", "riyadh": "RUH", "suudi arabistan": "RUH", "saudi arabia": "RUH",
    "amman": "AMM", "ürdün": "AMM", "jordan": "AMM",
    "beyrut": "BEY", "beirut": "BEY", "lübnan": "BEY", "lebanon": "BEY",
    # Kuzey Afrika
    "kahire": "CAI", "cairo": "CAI", "mısır": "CAI", "egypt": "CAI",
    "marakeş": "RAK", "marrakech": "RAK", "kazablanka": "CMN", "casablanca": "CMN",
    "fas": "CMN", "morocco": "CMN",
    "tunus": "TUN", "tunisia": "TUN",
    # Rusya / Ukrayna
    "moskova": "SVO", "moscow": "SVO", "rusya": "SVO", "russia": "SVO",
    "st. petersburg": "LED", "saint petersburg": "LED",
    # Asya
    "tokyo": "NRT", "osaka": "KIX", "kyoto": "KIX", "japonya": "NRT", "japan": "NRT",
    "pekin": "PEK", "beijing": "PEK", "şangay": "PVG", "shanghai": "PVG",
    "çin": "PEK", "china": "PEK",
    "hong kong": "HKG",
    "seoul": "ICN", "güney kore": "ICN", "south korea": "ICN",
    "bangkok": "BKK", "tayland": "BKK", "thailand": "BKK",
    "singapur": "SIN", "singapore": "SIN",
    "bali": "DPS", "jakarta": "CGK", "endonezya": "CGK", "indonesia": "CGK",
    "kuala lumpur": "KUL", "malezya": "KUL", "malaysia": "KUL",
    "manila": "MNL", "filipinler": "MNL", "philippines": "MNL",
    "hanoi": "HAN", "ho chi minh": "SGN", "vietnam": "HAN",
    "mumbai": "BOM", "delhi": "DEL", "hindistan": "DEL", "india": "DEL",
    # Maldivler / Seyşeller
    "maldivler": "MLE", "maldives": "MLE",
    "seyşeller": "SEZ", "seychelles": "SEZ",
    # Amerika
    "new york": "JFK", "los angeles": "LAX", "chicago": "ORD",
    "miami": "MIA", "san francisco": "SFO", "las vegas": "LAS",
    "toronto": "YYZ", "vancouver": "YVR", "montreal": "YUL",
    "mexico city": "MEX", "meksika": "MEX", "mexico": "MEX",
    "buenos aires": "EZE", "arjantin": "EZE", "argentina": "EZE",
    "sao paulo": "GRU", "rio de janeiro": "GIG", "brezilya": "GRU", "brazil": "GRU",
    # Okyanusya / Afrika
    "sydney": "SYD", "melbourne": "MEL", "avustralya": "SYD", "australia": "SYD",
    "cape town": "CPT", "johannesburg": "JNB", "nairobi": "NBO",
}

_TR_MAP = str.maketrans("ışğüöçİŞĞÜÖÇ", "isguocISGUOC")

def _norm(s: str) -> str:
    """Türkçe karakterleri ASCII'ye çevirir, küçültür."""
    return s.lower().translate(_TR_MAP)

def resolve_iata(raw: str) -> str:
    """Şehir/ülke adı veya IATA kodunu normalize eder."""
    if not raw:
        return ""
    s = raw.strip()
    # Zaten 2-3 harf IATA ise direkt döndür
    if len(s) <= 3 and s.isalpha():
        return s.upper()
    lower     = s.lower()
    lower_asc = _norm(s)          # Türkçe karaktersiz versiyon
    # Tam eşleşme (önce orijinal, sonra ASCII normalize)
    if lower in CITY_IATA:
        return CITY_IATA[lower]
    if lower_asc in CITY_IATA:
        return CITY_IATA[lower_asc]
    # Dict anahtarlarını da normalize edip karşılaştır
    for key, code in CITY_IATA.items():
        if _norm(key) == lower_asc:
            return code
    # Kısmi eşleşme
    for key, code in CITY_IATA.items():
        nk = _norm(key)
        if nk in lower_asc or lower_asc in nk:
            return code
    return s[:3].upper()

# ── Travelpayouts Uçuş Arama ──────────────────────────────────────────────────
_TP_HEADERS = {"X-Access-Token": TRAVELPAYOUTS_TOKEN, "Accept": "application/json"}

def _tp_get(endpoint: str, params: dict) -> dict:
    params["token"] = TRAVELPAYOUTS_TOKEN
    try:
        r = http.get(f"{TP_BASE}{endpoint}", params=params,
                     headers=_TP_HEADERS, timeout=15)
        print(f"  [TP] {r.status_code} {endpoint} — {r.url[:100]}")
        if r.status_code != 200:
            print(f"  Yanıt: {r.text[:200]}")
            return {}
        return r.json()
    except Exception as e:
        print(f"  TP hatası: {e}")
        return {}

def fetch_flights(origin: str, destination: str, dep_date: str,
                  ret_date: str, one_way: bool, direct: bool, currency: str = "EUR") -> list[dict]:
    # ── v3 prices_for_dates (günlük kesin tarih) ──────────────────────────
    p = {
        "origin": origin, "destination": destination,
        "departure_at": dep_date,
        "one_way": str(one_way).lower(), "direct": str(direct).lower(),
        "currency": currency.lower(), "market": "tr", "locale": "tr",
        "limit": 10, "sorting": "price",
    }
    if not one_way and ret_date:
        p["return_at"] = ret_date
    data = _tp_get("/aviasales/v3/prices_for_dates", p)
    results = data.get("data", []) if data.get("success") else []
    if results:
        return results

    # ── v1/prices/cheap fallback (ay bazlı, daha geniş kapsam) ───────────
    print("  v3 boş döndü, v1/prices/cheap deneniyor...")
    dep_month = dep_date[:7] if dep_date else ""   # YYYY-MM
    ret_month = ret_date[:7] if ret_date else ""
    p2 = {
        "origin": origin, "destination": destination,
        "depart_date": dep_month, "currency": currency.upper(),
    }
    if not one_way and ret_month:
        p2["return_date"] = ret_month
    data2 = _tp_get("/v1/prices/cheap", p2)
    raw2 = data2.get("data", {})
    currency_resp = data2.get("currency", currency.upper())
    # v1 format: {"DEST": {"0": {ticket}, "1": {ticket}}}
    # Key is destination IATA, inner key is number of stops
    normalized = []
    if isinstance(raw2, dict):
        for dest_key, stop_dict in raw2.items():
            if isinstance(stop_dict, dict):
                for stops_key, t in stop_dict.items():
                    if isinstance(t, dict):
                        normalized.append({
                            "origin":            origin,
                            "destination":       dest_key,
                            "airline":           t.get("airline", "?"),
                            "flight_number":     t.get("flight_number", ""),
                            "price":             t.get("price", 0),
                            "currency":          currency_resp,
                            "departure_at":      t.get("departure_at", dep_date),
                            "return_at":         t.get("return_at", ret_date),
                            "number_of_changes": int(stops_key) if stops_key.isdigit() else t.get("number_of_changes", 0),
                            "duration":          t.get("duration", 0),
                            "duration_to":       t.get("duration_to", t.get("duration", 0)),
                            "duration_back":     t.get("duration_back", 0),
                            "link":              t.get("link", ""),
                        })
    return sorted(normalized, key=lambda x: x.get("price", 0))[:10]

def format_flights_for_qwen(flights: list[dict], flight_type: str) -> str:
    if not flights:
        return "Uçuş verisi bulunamadı."
    lines = []
    for i, f in enumerate(flights, 1):
        dep = f.get("departure_at", "?")[:16].replace("T", " ")
        ret = f.get("return_at", "")
        ret_str = f" | Dönüş: {ret[:16].replace('T',' ')}" if ret else ""
        dur_to   = f.get("duration_to", f.get("duration", 0))
        dur_back = f.get("duration_back", 0)
        stops    = f.get("number_of_changes", 0)
        stops_str = "Direkt" if stops == 0 else f"{stops} aktarma"
        lines.append(
            f"{i}. {f.get('airline','?')} | "
            f"{f.get('price',0)} {f.get('currency','EUR')} | "
            f"Kalkış: {dep} | Süre: {dur_to}dk → {dur_back}dk | "
            f"{stops_str}{ret_str}"
        )
    return "\n".join(lines)

FLIGHT_ANALYSIS_FORMAT = {
    "best": {
        "index": 1,
        "airline": "TK",
        "price": 350,
        "currency": "EUR",
        "departure_at": "2026-06-15 08:30",
        "return_at": "2026-06-20 14:00",
        "number_of_changes": 0,
        "duration_to": 180,
        "duration_back": 210,
        "neden": "Neden bu uçuşu seçtim (1-2 cümle)"
    },
    "alternatives": [],
    "summary": "Genel değerlendirme (2-3 cümle)"
}

def analyze_flights_with_qwen(flights: list[dict], budget: str,
                               flight_type: str, city: str) -> dict | None:
    if not flights:
        return None

    flight_text = format_flights_for_qwen(flights, flight_type)
    system_prompt = f"""Sen bir AI Travel Planner servisinin uçuş analistisisin.
SADECE JSON çıktısı üret. ASLA açıklama yazma. ASLA markdown kullanma.

UÇUŞ VERİLERİ ({city} için {flight_type}):
{flight_text}

GÖREV:
- Uçuşları analiz et
- Kullanıcı bütçesine uygun olanları seç (bütçe: {budget})
- Çok uzun aktarmaları ele (3+ aktarma → önerme)
- Mantıklı kalkış saatlerini tercih et (06:00-22:00)
- Fiyat/performans açısından en uygun seçenekleri öne çıkar

ÖNCELİK SIRASI:
1. Bütçe uyumu
2. Toplam uçuş süresi
3. Aktarma sayısı
4. Kalkış saati uygunluğu

Uçuş uydurma. Sadece verilen API verileri üzerinden karar ver.
Eğer hiç uygun uçuş yoksa best'i null yap.

KULLANMAN GEREKEN JSON FORMAT:
{json.dumps(FLIGHT_ANALYSIS_FORMAT, ensure_ascii=False)}

OUTPUT: SADECE GEÇERLİ JSON"""

    user_prompt = f"Destinasyon: {city} | Bütçe: {budget} | Uçuş türü: {flight_type}"

    for attempt in range(1, 3):
        print(f"  [Qwen/Uçuş] Deneme {attempt}/2...", end=" ", flush=True)
        raw = call_qwen(user_prompt, system_prompt)
        result = clean_and_parse(raw)
        if result and "best" in result:
            print("OK")
            # Orijinal flight datasını best'e ekle
            best_idx = result["best"].get("index", 1) - 1
            if 0 <= best_idx < len(flights):
                result["_raw_best"] = flights[best_idx]
            return result
        print("parse hatası")
    return None

# ── HTTP Server ───────────────────────────────────────────────────────────────
class TripsoHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"  [{datetime.now().strftime('%H:%M:%S')}] {fmt % args}")

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _html(self, path: str):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._html(os.path.join(os.path.dirname(__file__), "tripso_web.html"))
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", 0))
            body   = json.loads(self.rfile.read(length)) if length else {}

            if parsed.path == "/api/plan":
                self._handle_plan(body)
            elif parsed.path == "/api/flights":
                self._handle_flights(body)
            else:
                self._json({"error": "Bilinmeyen endpoint"}, 404)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            try:
                self._json({"error": f"Sunucu hatası: {exc}"}, 500)
            except Exception:
                pass

    # ── /api/plan ─────────────────────────────────────────────────────────────
    def _handle_plan(self, raw: dict):
        mode_str = raw.pop("_mode", "plan")
        mode     = MODE_PLAN if mode_str == "plan" else MODE_VENUE

        try:
            params = parse_trip_request(raw)
        except Exception as e:
            import traceback; traceback.print_exc()
            self._json({"error": f"Payload parse hatası: {e}"}, 400)
            return

        print(f"\n[PLAN] {params['city']} | {params['days']} gün | {params['budget']} | {mode_str}")

        places  = fetch_places(params["city"], params["travel_focus"],
                               params["must_see"], params["profile_interests"], mode)
        context = format_places_for_prompt(places)
        u_prompt = build_user_prompt(params, mode)
        s_prompt = (build_system_prompt_plan(params, context) if mode == MODE_PLAN
                    else build_system_prompt_venue(params, context))
        validate  = validate_plan_json if mode == MODE_PLAN else validate_venue_json

        plan_data = None
        for attempt in range(1, MAX_RETRY + 1):
            print(f"  [Qwen/Plan] Deneme {attempt}/{MAX_RETRY}...", end=" ", flush=True)
            raw_resp = call_qwen(u_prompt, s_prompt)
            data     = clean_and_parse(raw_resp)
            if data is None:
                print("JSON parse hatası"); continue
            ok, msg = validate(data)
            if ok:
                plan_data = data; print("OK"); break
            print(f"Validasyon: {msg}")

        self._json({
            "mode":    mode_str,
            "plan":    plan_data,
            "params":  params,
            "success": plan_data is not None,
        })

    # ── /api/flights ──────────────────────────────────────────────────────────
    def _handle_flights(self, body: dict):
        try:
            origin_raw  = (body.get("origin") or "").strip()
            dest_city   = body.get("destinationCity", "").strip()
            flight_type = body.get("flightType", "round")
            direct      = body.get("direct", False)
            budget      = body.get("budget", "mid")
            currency    = body.get("currency", "EUR")
            dep_date    = (body.get("departureDate") or "")[:10]
            ret_date    = (body.get("returnDate") or "")[:10]

            # Şehir adını veya IATA'yı normalize et
            origin    = resolve_iata(origin_raw)
            dest_iata = resolve_iata(dest_city)

            if not origin:
                self._json({"error": "Kalkış şehri veya IATA kodu girilmedi."}, 400); return
            if not dest_iata:
                self._json({"error": f'"{dest_city}" için havalimanı kodu bulunamadı.'}, 400); return
            if not dep_date:
                self._json({"error": "Kalkış tarihi girilmedi."}, 400); return

            print(f"\n[FLIGHTS] {origin_raw!r}->{origin} | {dest_city!r}->{dest_iata} | {dep_date}→{ret_date} | {flight_type}")

            flights = []
            if flight_type == "round":
                flights = fetch_flights(origin, dest_iata, dep_date, ret_date, False, direct, currency)
            elif flight_type == "outbound":
                flights = fetch_flights(origin, dest_iata, dep_date, "", True, direct, currency)
            elif flight_type == "inbound":
                flights = fetch_flights(dest_iata, origin, ret_date or dep_date, "", True, direct, currency)

            analysis = analyze_flights_with_qwen(flights, budget, flight_type, dest_city) if flights else None

            self._json({
                "origin":      origin,
                "destination": dest_iata,
                "flightType":  flight_type,
                "rawFlights":  flights,
                "analysis":    analysis,
                "count":       len(flights),
            })
        except Exception as exc:
            import traceback; traceback.print_exc()
            self._json({"error": f"Uçuş arama hatası: {exc}"}, 500)


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    from qwen_test import GEOAPIFY_KEY as _GEO_KEY, OLLAMA_URL as _OLLAMA, MODEL as _MODEL
    print("=" * 56)
    print("  TRIPSO Dev Server")
    print("=" * 56)
    print(f"  Dashboard       : http://localhost:{PORT}")
    print(f"  Backend         : http://localhost:3000")
    print(f"  Travelpayouts   : {'OK  (' + TRAVELPAYOUTS_TOKEN[:8] + '...)' if TRAVELPAYOUTS_TOKEN else 'YOK — .env dosyasini kontrol et'}")
    print(f"  Geoapify        : {'OK  (' + _GEO_KEY[:8] + '...)' if _GEO_KEY else 'YOK — .env dosyasini kontrol et'}")
    print(f"  Ollama          : {_OLLAMA}  [{_MODEL}]")
    print("=" * 56)
    server = HTTPServer(("0.0.0.0", PORT), TripsoHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Sunucu durduruldu.")
