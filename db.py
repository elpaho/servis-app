"""
Sloj za bazu (SQLite).

- Podaci žive u data\\ mapi IZVAN foldera verzije (vidi get_data_dir).
- Verzija sheme je u PRAGMA user_version. Migracije se izvršavaju redom pri
  svakom pokretanju; prije migracije radi se sigurnosna kopija baze.
- Nova promjena sheme = NOVA stavka na kraj liste MIGRATIONS. Postojeće
  stavke se nikad ne mijenjaju.
"""
import hashlib
import hmac
import os
import shutil
import sqlite3
import unicodedata
from datetime import date, datetime

import paths

STATUS_OTVOREN = "otvoren"
STATUS_GOTOV = "gotov"
STATUS_PREUZET = "preuzet"

DEFAULT_SETTINGS = {
    "dana_u_servisu": "7",     # N: istakni naloge koji su toliko dana u servisu
    "dana_do_roka": "2",       # M: istakni naloge kojima rok ističe za toliko dana
    "auto_preuzet": "0",       # 1 = nalog se pri završetku odmah označi kao preuzet
}


def get_data_dir() -> str:
    """Mapa s podacima (vidi paths.py): produkcija FAMILY_ROOT\\data, razvoj .\\data."""
    return paths.data_dir()


def normalize(text: str) -> str:
    """'Čorić' -> 'coric', 'Đuro'/'Djuro' -> 'duro'. Za pretragu bez obzira na dijakritike i velika slova."""
    if not text:
        return ""
    text = text.replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # "dj" i "đ" se tipkaju zamjenski (Djuro/Đuro): oboje se svodi na "d", i u bazi i u upitu
    return text.lower().replace("dj", "d").strip()


# ---------------------------------------------------------------- migracije
MIGRATIONS = [
    # 1: početna shema
    """
    CREATE TABLE klijent (
        id INTEGER PRIMARY KEY,
        naziv TEXT NOT NULL,
        naziv_pretraga TEXT NOT NULL,
        telefon TEXT NOT NULL DEFAULT '',
        email TEXT NOT NULL DEFAULT '',
        napomena TEXT NOT NULL DEFAULT '',
        aktivan INTEGER NOT NULL DEFAULT 1
    );
    CREATE INDEX idx_klijent_pretraga ON klijent(naziv_pretraga);

    CREATE TABLE bicikl (
        id INTEGER PRIMARY KEY,
        klijent_id INTEGER NOT NULL REFERENCES klijent(id),
        naziv TEXT NOT NULL,
        napomena TEXT NOT NULL DEFAULT '',
        aktivan INTEGER NOT NULL DEFAULT 1
    );
    CREATE INDEX idx_bicikl_klijent ON bicikl(klijent_id);

    CREATE TABLE korisnik (
        id INTEGER PRIMARY KEY,
        ime TEXT NOT NULL,
        pin_hash TEXT NOT NULL DEFAULT '',
        aktivan INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE nalog (
        id INTEGER PRIMARY KEY,
        broj TEXT NOT NULL UNIQUE,
        bicikl_id INTEGER NOT NULL REFERENCES bicikl(id),
        datum_zaprimanja TEXT NOT NULL,
        rok TEXT,
        datum_zavrsetka TEXT,
        datum_preuzimanja TEXT,
        status TEXT NOT NULL DEFAULT 'otvoren'
            CHECK (status IN ('otvoren', 'gotov', 'preuzet')),
        opis_klijent TEXT NOT NULL DEFAULT '',
        opis_radova TEXT NOT NULL DEFAULT '',
        otvorio_korisnik_id INTEGER REFERENCES korisnik(id),
        zatvorio_korisnik_id INTEGER REFERENCES korisnik(id)
    );
    CREATE INDEX idx_nalog_status ON nalog(status);
    CREATE INDEX idx_nalog_bicikl ON nalog(bicikl_id);

    CREATE TABLE postavke (
        kljuc TEXT PRIMARY KEY,
        vrijednost TEXT NOT NULL
    );
    """,
]


def connect(path: str = None) -> sqlite3.Connection:
    if path is None:
        path = os.path.join(get_data_dir(), "servis.db")
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate(conn, path)
    _ensure_default_settings(conn)
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migrate(conn: sqlite3.Connection, path: str):
    current = schema_version(conn)
    target = len(MIGRATIONS)
    if current > target:
        raise RuntimeError(
            f"Baza je novije verzije ({current}) nego što ova aplikacija zna ({target}). "
            "Pokrenuta je starija verzija aplikacije; ažuriraj aplikaciju."
        )
    if current == target:
        return

    # sigurnosna kopija prije mijenjanja postojeće baze
    if current > 0 and os.path.isfile(path):
        backup_dir = os.path.join(os.path.dirname(path), "backup")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, os.path.join(backup_dir, f"servis_pre_v{current}_{stamp}.db"))

    for version in range(current, target):
        conn.executescript("BEGIN;" + MIGRATIONS[version] + f"PRAGMA user_version = {version + 1}; COMMIT;")


def _ensure_default_settings(conn: sqlite3.Connection):
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute("INSERT OR IGNORE INTO postavke(kljuc, vrijednost) VALUES (?, ?)", (k, v))
    conn.commit()


# ---------------------------------------------------------------- postavke
def get_setting(conn, key: str) -> str:
    row = conn.execute("SELECT vrijednost FROM postavke WHERE kljuc = ?", (key,)).fetchone()
    return row["vrijednost"] if row else DEFAULT_SETTINGS[key]


def set_setting(conn, key: str, value):
    conn.execute(
        "INSERT INTO postavke(kljuc, vrijednost) VALUES (?, ?) "
        "ON CONFLICT(kljuc) DO UPDATE SET vrijednost = excluded.vrijednost",
        (key, str(value)),
    )
    conn.commit()


# ---------------------------------------------------------------- klijenti
def add_klijent(conn, naziv, telefon="", email="", napomena="") -> int:
    cur = conn.execute(
        "INSERT INTO klijent(naziv, naziv_pretraga, telefon, email, napomena) VALUES (?,?,?,?,?)",
        (naziv.strip(), normalize(naziv), telefon.strip(), email.strip(), napomena.strip()),
    )
    conn.commit()
    return cur.lastrowid


def search_klijenti(conn, query: str, limit: int = 50):
    """Svaka riječ upita mora se pojaviti u nazivu ili telefonu (bez dijakritika)."""
    words = normalize(query).split()
    if not words:
        return []
    where, params = [], []
    for w in words:
        where.append("(naziv_pretraga LIKE ? OR REPLACE(telefon, ' ', '') LIKE ?)")
        params += [f"%{w}%", f"%{w}%"]
    sql = f"SELECT * FROM klijent WHERE aktivan = 1 AND {' AND '.join(where)} ORDER BY naziv_pretraga LIMIT ?"
    return conn.execute(sql, params + [limit]).fetchall()


def add_bicikl(conn, klijent_id, naziv, napomena="") -> int:
    cur = conn.execute(
        "INSERT INTO bicikl(klijent_id, naziv, napomena) VALUES (?,?,?)",
        (klijent_id, naziv.strip(), napomena.strip()),
    )
    conn.commit()
    return cur.lastrowid


def bicikli_klijenta(conn, klijent_id):
    return conn.execute(
        "SELECT * FROM bicikl WHERE klijent_id = ? AND aktivan = 1 ORDER BY naziv", (klijent_id,)
    ).fetchall()


# ---------------------------------------------------------------- korisnici / PIN
def _hash_pin(pin: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 100_000)
    return salt.hex() + "$" + digest.hex()


def add_korisnik(conn, ime, pin="") -> int:
    cur = conn.execute(
        "INSERT INTO korisnik(ime, pin_hash) VALUES (?, ?)", (ime.strip(), _hash_pin(pin) if pin else "")
    )
    conn.commit()
    return cur.lastrowid


def check_pin(conn, korisnik_id: int, pin: str) -> bool:
    row = conn.execute("SELECT pin_hash FROM korisnik WHERE id = ? AND aktivan = 1", (korisnik_id,)).fetchone()
    if row is None:
        return False
    if not row["pin_hash"]:
        return True  # korisnik bez PIN-a
    salt_hex, _ = row["pin_hash"].split("$", 1)
    return hmac.compare_digest(_hash_pin(pin, bytes.fromhex(salt_hex)), row["pin_hash"])


# ---------------------------------------------------------------- nalozi
def _next_broj(conn, year: int) -> str:
    prefix = f"{year}-"
    row = conn.execute(
        "SELECT MAX(CAST(SUBSTR(broj, 6) AS INTEGER)) AS m FROM nalog WHERE broj LIKE ?", (prefix + "%",)
    ).fetchone()
    return f"{prefix}{(row['m'] or 0) + 1:04d}"


def open_nalog(conn, bicikl_id, opis_klijent="", rok=None, korisnik_id=None, today: date = None) -> int:
    today = today or date.today()
    broj = _next_broj(conn, today.year)
    cur = conn.execute(
        "INSERT INTO nalog(broj, bicikl_id, datum_zaprimanja, rok, opis_klijent, otvorio_korisnik_id) "
        "VALUES (?,?,?,?,?,?)",
        (broj, bicikl_id, today.isoformat(), rok, opis_klijent.strip(), korisnik_id),
    )
    conn.commit()
    return cur.lastrowid


def finish_nalog(conn, nalog_id, opis_radova, korisnik_id=None, today: date = None):
    today = today or date.today()
    if get_setting(conn, "auto_preuzet") == "1":
        status, preuzet = STATUS_PREUZET, today.isoformat()
    else:
        status, preuzet = STATUS_GOTOV, None
    conn.execute(
        "UPDATE nalog SET status = ?, datum_zavrsetka = ?, datum_preuzimanja = ?, "
        "opis_radova = ?, zatvorio_korisnik_id = ? WHERE id = ?",
        (status, today.isoformat(), preuzet, opis_radova.strip(), korisnik_id, nalog_id),
    )
    conn.commit()


def mark_preuzet(conn, nalog_id, today: date = None):
    today = today or date.today()
    conn.execute(
        "UPDATE nalog SET status = ?, datum_preuzimanja = ? WHERE id = ? AND status = ?",
        (STATUS_PREUZET, today.isoformat(), nalog_id, STATUS_GOTOV),
    )
    conn.commit()


_NALOG_SELECT = """
    SELECT n.*, b.naziv AS bicikl_naziv, k.id AS klijent_id, k.naziv AS klijent_naziv, k.telefon AS klijent_telefon
    FROM nalog n
    JOIN bicikl b ON b.id = n.bicikl_id
    JOIN klijent k ON k.id = b.klijent_id
"""


def list_nalozi(conn, status: str, today: date = None):
    """Nalozi za pregled sa zastavicama isticanja. status: otvoren | gotov | preuzet."""
    rows = conn.execute(_NALOG_SELECT + " WHERE n.status = ? ORDER BY n.datum_zaprimanja", (status,)).fetchall()
    return [_with_flags(conn, r, today) for r in rows]


def _with_flags(conn, row, today: date = None) -> dict:
    """
    Dodaje: dana_u_servisu, upozorenje (tekst), boja ('crvena' | 'zuta' | ''), hitnost (za sortiranje).
    Crveno: rok je prošao ILI je nalog u servisu N ili više dana.
    Žuto:   rok ističe za M ili manje dana.
    Samo za otvorene naloge.
    """
    today = today or date.today()
    d = dict(row)
    d["dana_u_servisu"] = (today - date.fromisoformat(d["datum_zaprimanja"])).days
    d["upozorenje"], d["boja"], d["hitnost"] = "", "", 0
    if d["status"] != STATUS_OTVOREN:
        return d

    n = int(get_setting(conn, "dana_u_servisu"))
    m = int(get_setting(conn, "dana_do_roka"))
    texts = []
    if d["rok"]:
        do_roka = (date.fromisoformat(d["rok"]) - today).days
        if do_roka < 0:
            texts.append(f"Kasni {-do_roka} dan(a)")
            d["hitnost"] = 3
        elif do_roka <= m:
            texts.append("Rok danas" if do_roka == 0 else f"Rok za {do_roka} dan(a)")
            d["hitnost"] = 2
    if d["dana_u_servisu"] >= n:
        texts.append(f"{d['dana_u_servisu']} dana u servisu")
        d["hitnost"] = 3
    d["upozorenje"] = " · ".join(texts)
    d["boja"] = {3: "crvena", 2: "zuta"}.get(d["hitnost"], "")
    return d


def sort_by_urgency(nalozi):
    return sorted(nalozi, key=lambda d: (-d["hitnost"], d["datum_zaprimanja"]))
