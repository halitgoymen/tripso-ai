import json
import sys
import requests
from getpass import getpass

BASE_URL = "http://localhost:3000"

# ── ANSI Renkleri ─────────────────────────────────────────────────────────────
R  = "\033[91m"   # kırmızı
G  = "\033[92m"   # yeşil
Y  = "\033[93m"   # sarı
B  = "\033[94m"   # mavi
C  = "\033[96m"   # cyan
W  = "\033[97m"   # beyaz
DIM = "\033[2m"   # soluk
RST = "\033[0m"   # sıfırla
BOLD = "\033[1m"  # kalın

# ── Oturum ────────────────────────────────────────────────────────────────────
session = {
    "access_token":  None,
    "refresh_token": None,
    "user":          None,
}


# ── Yardımcılar ───────────────────────────────────────────────────────────────
def clear():
    print("\033[2J\033[H", end="")


def divider(char="─", width=54):
    print(f"{DIM}{char * width}{RST}")


def header(title: str):
    clear()
    divider("═")
    print(f"{BOLD}{C}  TRIPSO  {RST}{W}— {title}{RST}")
    divider("═")
    print()


def ok(msg: str):
    print(f"\n  {G}✔{RST}  {msg}")


def err(msg: str):
    print(f"\n  {R}✘{RST}  {msg}")


def info(msg: str):
    print(f"  {DIM}{msg}{RST}")


def ask(label: str, default: str = "", secret: bool = False) -> str:
    hint = f" {DIM}[{default}]{RST}" if default else ""
    prompt = f"  {Y}›{RST} {label}{hint}: "
    if secret:
        val = getpass(prompt)
    else:
        val = input(prompt).strip()
    return val if val else default


def ask_optional(label: str, current=None) -> str:
    hint = f" {DIM}[{current or 'boş'}]{RST}"
    val = input(f"  {Y}›{RST} {label}{hint}: ").strip()
    return val if val else (current or "")


def print_json(data: dict):
    print()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def _post(path: str, body: dict, auth: bool = False) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    if auth:
        headers.update(auth_headers())
    try:
        r = requests.post(f"{BASE_URL}{path}", json=body, headers=headers, timeout=10)
        return r.status_code, _safe_json(r)
    except requests.exceptions.ConnectionError:
        err("Backend'e bağlanılamadı. Server çalışıyor mu? (npm run dev)")
        return 0, {}


def _get(path: str) -> tuple[int, dict]:
    try:
        r = requests.get(f"{BASE_URL}{path}", headers=auth_headers(), timeout=10)
        return r.status_code, _safe_json(r)
    except requests.exceptions.ConnectionError:
        err("Backend'e bağlanılamadı. Server çalışıyor mu? (npm run dev)")
        return 0, {}


def _patch(path: str, body: dict) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json"}
    headers.update(auth_headers())
    try:
        r = requests.patch(f"{BASE_URL}{path}", json=body, headers=headers, timeout=10)
        return r.status_code, _safe_json(r)
    except requests.exceptions.ConnectionError:
        err("Backend'e bağlanılamadı. Server çalışıyor mu? (npm run dev)")
        return 0, {}


def _safe_json(r: requests.Response) -> dict:
    try:
        return r.json()
    except Exception:
        return {"raw": r.text}


def print_errors(data: dict):
    msg = data.get("message")
    if isinstance(msg, list):
        for m in msg:
            err(m)
    elif msg:
        err(msg)
    else:
        err(json.dumps(data, ensure_ascii=False))


# ── Kullanıcı Gösterimi ───────────────────────────────────────────────────────
def print_user(user: dict):
    divider()
    fields = [
        ("ID",              user.get("id")),
        ("Ad",              user.get("name")),
        ("E-posta",         user.get("email")),
        ("Zaman dilimi",    user.get("timezone")),
        ("Dil",             user.get("locale")),
        ("Şehir",           user.get("homeCity")         or "—"),
        ("Havalimanı kodu", user.get("homeAirportCode")  or "—"),
        ("Kayıt tarihi",    user.get("createdAt")),
    ]
    for label, val in fields:
        print(f"  {DIM}{label:<18}{RST}{W}{val}{RST}")
    divider()


def print_profile(profile: dict):
    divider()
    if not profile:
        print(f"  {DIM}Henüz seyahat profili oluşturulmamış.{RST}")
        divider()
        return
    fields = [
        ("Diyet",           ", ".join(profile.get("dietary", [])) or "—"),
        ("Alkol",           profile.get("alcohol")),
        ("Konaklama",       profile.get("accommodationTier")),
        ("Tempo",           profile.get("pace")),
        ("Ulaşım",          profile.get("transportationStyle")),
        ("Fiziksel",        profile.get("physicalCapability")),
        ("İlgi alanları",   ", ".join(profile.get("interests", [])) or "—"),
        ("Diller",          ", ".join(profile.get("languages", [])) or "—"),
        ("Yaş grubu",       profile.get("ageGroup")),
        ("Deneyim",         profile.get("travelExperience")),
    ]
    for label, val in fields:
        print(f"  {DIM}{label:<18}{RST}{W}{val}{RST}")
    divider()


# ── Auth ──────────────────────────────────────────────────────────────────────
def do_register():
    header("Kayıt Ol")
    name     = ask("Adınız")
    email    = ask("E-posta")
    password = ask("Şifre (min 8 karakter)", secret=True)

    if not name or not email or not password:
        err("Tüm alanlar zorunludur.")
        input(f"\n  {DIM}Devam etmek için Enter...{RST}")
        return

    status, data = _post("/auth/register", {
        "name": name, "email": email, "password": password
    })

    if status == 201:
        session["access_token"]  = data["accessToken"]
        session["refresh_token"] = data["refreshToken"]
        session["user"]          = data["user"]
        ok(f"Kayıt başarılı! Hoş geldin, {B}{data['user']['name']}{RST}")
        print_user(data["user"])
    else:
        print_errors(data)

    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


def do_login():
    header("Giriş Yap")
    email    = ask("E-posta")
    password = ask("Şifre", secret=True)

    if not email or not password:
        err("E-posta ve şifre zorunludur.")
        input(f"\n  {DIM}Devam etmek için Enter...{RST}")
        return

    status, data = _post("/auth/login", {"email": email, "password": password})

    if status == 200:
        session["access_token"]  = data["accessToken"]
        session["refresh_token"] = data["refreshToken"]
        session["user"]          = data["user"]
        ok(f"Giriş başarılı! Hoş geldin, {B}{data['user']['name']}{RST}")
        print_user(data["user"])
    else:
        print_errors(data)

    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


def do_refresh():
    if not session["refresh_token"]:
        err("Önce giriş yapmalısınız.")
        input(f"\n  {DIM}Devam etmek için Enter...{RST}")
        return

    status, data = _post("/auth/refresh", {"refreshToken": session["refresh_token"]})
    if status == 200:
        session["access_token"]  = data["accessToken"]
        session["refresh_token"] = data["refreshToken"]
        ok("Token yenilendi.")
    else:
        print_errors(data)

    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


# ── Kullanıcı İşlemleri ───────────────────────────────────────────────────────
def do_get_me():
    header("Hesap Bilgileri")
    status, data = _get("/users/me")
    if status == 200:
        session["user"] = data
        print_user(data)
    else:
        print_errors(data)
    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


def do_update_me():
    header("Hesap Güncelle")
    user = session.get("user") or {}
    info("Boş bırakırsanız mevcut değer korunur.\n")

    body = {}

    name = ask_optional("Ad", user.get("name"))
    if name and name != user.get("name"):
        body["name"] = name

    timezone = ask_optional("Zaman dilimi", user.get("timezone", "UTC"))
    if timezone and timezone != user.get("timezone"):
        body["timezone"] = timezone

    locale = ask_optional("Dil (örn. tr-TR)", user.get("locale", "en-US"))
    if locale and locale != user.get("locale"):
        body["locale"] = locale

    home_city = ask_optional("Şehir", user.get("homeCity"))
    if home_city != (user.get("homeCity") or ""):
        body["homeCity"] = home_city or None

    airport = ask_optional("Havalimanı kodu (örn. IST)", user.get("homeAirportCode"))
    airport = airport.upper() if airport else ""
    if airport != (user.get("homeAirportCode") or ""):
        body["homeAirportCode"] = airport or None

    if not body:
        info("Değişiklik yok.")
        input(f"\n  {DIM}Devam etmek için Enter...{RST}")
        return

    status, data = _patch("/users/me", body)
    if status == 200:
        session["user"] = data
        ok("Hesap güncellendi.")
        print_user(data)
    else:
        print_errors(data)

    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


def do_get_profile():
    header("Seyahat Profili")
    status, data = _get("/users/me/profile")
    if status == 200:
        print_profile(data)
    else:
        print_errors(data)
    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


def do_update_profile():
    header("Seyahat Profili Güncelle")
    info("Boş bırakırsanız değişmez. Listeler virgülle ayrılır.\n")

    ALCOHOL_OPTS      = ["yes", "no", "occasional"]
    ACCOM_OPTS        = ["economy", "standard", "comfort", "luxury"]
    PACE_OPTS         = ["relaxed", "balanced", "intense"]
    TRANSPORT_OPTS    = ["car", "public", "neutral"]
    PHYSICAL_OPTS     = ["high", "medium", "low", "accessible_needed"]

    def ask_enum(label, choices, current=""):
        opts = " / ".join(choices)
        while True:
            val = ask_optional(f"{label} ({opts})", current)
            if val in choices or val == "":
                return val if val else current
            err(f"Geçerli seçenekler: {opts}")

    body = {}

    dietary_raw = ask_optional("Diyet kısıtları (virgülle)")
    if dietary_raw:
        body["dietary"] = [d.strip() for d in dietary_raw.split(",") if d.strip()]

    alcohol = ask_enum("Alkol", ALCOHOL_OPTS)
    if alcohol:
        body["alcohol"] = alcohol

    accom = ask_enum("Konaklama", ACCOM_OPTS)
    if accom:
        body["accommodationTier"] = accom

    pace = ask_enum("Tempo", PACE_OPTS)
    if pace:
        body["pace"] = pace

    transport = ask_enum("Ulaşım", TRANSPORT_OPTS)
    if transport:
        body["transportationStyle"] = transport

    physical = ask_enum("Fiziksel kapasite", PHYSICAL_OPTS)
    if physical:
        body["physicalCapability"] = physical

    interests_raw = ask_optional("İlgi alanları (virgülle)")
    if interests_raw:
        body["interests"] = [i.strip() for i in interests_raw.split(",") if i.strip()]

    languages_raw = ask_optional("Diller (virgülle, örn. tr,en)")
    if languages_raw:
        body["languages"] = [l.strip() for l in languages_raw.split(",") if l.strip()]

    age_group = ask_optional("Yaş grubu (adult / senior / student...)")
    if age_group:
        body["ageGroup"] = age_group

    travel_exp = ask_optional("Seyahat deneyimi (beginner / experienced...)")
    if travel_exp:
        body["travelExperience"] = travel_exp

    if not body:
        info("Değişiklik yok.")
        input(f"\n  {DIM}Devam etmek için Enter...{RST}")
        return

    status, data = _patch("/users/me/profile", body)
    if status == 200:
        ok("Seyahat profili güncellendi.")
        print_profile(data)
    else:
        print_errors(data)

    input(f"\n  {DIM}Devam etmek için Enter...{RST}")


# ── Sağlık Kontrolü ───────────────────────────────────────────────────────────
def do_health():
    header("Sunucu Durumu")
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        status, data = r.status_code, _safe_json(r)
        if status == 200:
            ok(f"Server çalışıyor  {DIM}({BASE_URL}){RST}")
        else:
            err(f"Server yanıt verdi ama durum: {status}")
        print_json(data)
    except requests.exceptions.ConnectionError:
        err(f"Server'a ulaşılamıyor: {BASE_URL}")
        info("tripso-backend-main klasöründe 'npm run dev' çalıştırın.")
        print()
    input(f"  {DIM}Devam etmek için Enter...{RST}")


# ── Menüler ───────────────────────────────────────────────────────────────────
def menu_auth():
    while True:
        user_label = session["user"]["name"] if session["user"] else None
        header("Giriş Gerekli" if not user_label else f"Giriş: {B}{user_label}{RST}")

        logged_in = session["access_token"] is not None

        if not logged_in:
            print(f"  {W}[1]{RST}  Kayıt ol")
            print(f"  {W}[2]{RST}  Giriş yap")
            print(f"  {W}[3]{RST}  Sunucu durumu")
            print(f"  {W}[0]{RST}  Çıkış")
        else:
            print(f"  {W}[1]{RST}  Hesap bilgileri")
            print(f"  {W}[2]{RST}  Hesap güncelle")
            print(f"  {W}[3]{RST}  Seyahat profili görüntüle")
            print(f"  {W}[4]{RST}  Seyahat profili güncelle")
            print(f"  {W}[5]{RST}  Token yenile")
            print(f"  {W}[6]{RST}  Sunucu durumu")
            print(f"  {W}[9]{RST}  Çıkış yap (oturumu kapat)")
            print(f"  {W}[0]{RST}  Programdan çık")

        print()
        divider()
        choice = input(f"  {Y}Seçiminiz:{RST} ").strip()
        print()

        if not logged_in:
            if choice == "1":
                do_register()
            elif choice == "2":
                do_login()
            elif choice == "3":
                do_health()
            elif choice == "0":
                print(f"\n  {DIM}Görüşmek üzere!{RST}\n")
                sys.exit(0)
        else:
            if choice == "1":
                do_get_me()
            elif choice == "2":
                do_update_me()
            elif choice == "3":
                do_get_profile()
            elif choice == "4":
                do_update_profile()
            elif choice == "5":
                do_refresh()
            elif choice == "6":
                do_health()
            elif choice == "9":
                session["access_token"]  = None
                session["refresh_token"] = None
                session["user"]          = None
                ok("Oturum kapatıldı.")
                input(f"\n  {DIM}Devam etmek için Enter...{RST}")
            elif choice == "0":
                print(f"\n  {DIM}Görüşmek üzere!{RST}\n")
                sys.exit(0)


# ── Giriş Noktası ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        menu_auth()
    except KeyboardInterrupt:
        print(f"\n\n  {DIM}İptal edildi.{RST}\n")
        sys.exit(0)
