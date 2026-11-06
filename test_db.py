import os, tempfile
from datetime import date
import db

d = tempfile.mkdtemp()
path = os.path.join(d, "servis.db")
conn = db.connect(path)
assert db.schema_version(conn) == len(db.MIGRATIONS)

# pretraga bez dijakritika
k1 = db.add_klijent(conn, "Marija Čorić", telefon="091 123 4567")
k2 = db.add_klijent(conn, "Đuro Šimić")
assert [r["naziv"] for r in db.search_klijenti(conn, "coric")] == ["Marija Čorić"]
assert [r["naziv"] for r in db.search_klijenti(conn, "djuro simic")] == ["Đuro Šimić"]
assert [r["naziv"] for r in db.search_klijenti(conn, "0911234567")] == ["Marija Čorić"]
assert db.search_klijenti(conn, "") == []

b1 = db.add_bicikl(conn, k1, "Trek Marlin")
b2 = db.add_bicikl(conn, k2, "Scott Addict")
# prvi korisnik "Serviser" nastaje sam, bez lozinke, i prijava bez lozinke radi
prvi = db.list_korisnici(conn)
assert [r["ime"] for r in prvi] == ["Serviser"] and not prvi[0]["ima_lozinku"]
assert db.check_lozinka(conn, prvi[0]["id"], "") and db.check_lozinka(conn, prvi[0]["id"], "bilo što")
u = db.add_korisnik(conn, "Marko", "1234")
assert db.check_lozinka(conn, u, "1234") and not db.check_lozinka(conn, u, "0000") and not db.check_lozinka(conn, u, "")
assert db.get_korisnik(conn, u)["ima_lozinku"] and "lozinka_hash" not in db.get_korisnik(conn, u).keys()

today = date(2026, 11, 6)
n1 = db.open_nalog(conn, b1, "cuje lanac", rok="2026-11-07", korisnik_id=u, today=date(2026,11,2))
n2 = db.open_nalog(conn, b2, "kočnice", rok="2026-11-05", today=date(2026,10,28))
n3 = db.open_nalog(conn, b1, "gume", rok="2026-11-20", today=today)
n4 = db.open_nalog(conn, b2, "općenito", today=date(2026,10,26))
brojevi = [r["broj"] for r in conn.execute("SELECT broj FROM nalog ORDER BY id")]
assert brojevi == ["2026-0001","2026-0002","2026-0003","2026-0004"], brojevi
assert db.open_nalog(conn, b1, today=date(2027,1,3)) and conn.execute("SELECT broj FROM nalog ORDER BY id DESC LIMIT 1").fetchone()[0]=="2027-0001"

rows = db.sort_by_urgency(db.list_nalozi(conn, "otvoren", today))
rows = [r for r in rows if r["broj"].startswith("2026")]
out = [(r["broj"], r["upozorenje"]) for r in rows]
print(out)
assert out[0] == ("2026-0004", "11 dana u servisu")            # crveno, najstariji
assert out[1] == ("2026-0002", "Kasni 1 dan · 9 dana u servisu")  # crveno
assert out[2] == ("2026-0001", "Rok za 1 dan")              # žuto
assert out[3] == ("2026-0003", "")
assert [r["boja"] for r in rows] == ["crvena", "crvena", "zuta", ""]

assert [db.dana(n) for n in (0,1,2,4,5,11,12,21,22,25,101,111)] == \
    ["0 dana","1 dan","2 dana","4 dana","5 dana","11 dana","12 dana","21 dan","22 dana","25 dana","101 dan","111 dana"]

# završetak + preuzimanje, ručno
db.finish_nalog(conn, n1, "zamijenjen lanac", korisnik_id=u, today=today)
r = conn.execute("SELECT status, datum_preuzimanja FROM nalog WHERE id=?", (n1,)).fetchone()
assert (r[0], r[1]) == ("gotov", None)
db.mark_preuzet(conn, n1, korisnik_id=prvi[0]["id"], today=today)
g = db.get_nalog(conn, n1)
assert g["status"] == "preuzet" and g["otvorio_ime"] == "Marko" and g["odradio_ime"] == "Marko" and g["predao_ime"] == "Serviser"

# auto_preuzet
db.set_setting(conn, "auto_preuzet", 1)
db.finish_nalog(conn, n3, "gume", korisnik_id=u, today=today)
g = db.get_nalog(conn, n3)
assert g["status"] == "preuzet" and g["odradio_ime"] == "Marko" and g["predao_ime"] == "Marko"   # auto: predao = odradio

# get_nalog / update_nalog
g = db.get_nalog(conn, n2, today)
assert g["klijent_naziv"] == "Đuro Šimić" and g["bicikl_naziv"] == "Scott Addict" and g["boja"] == "crvena"
assert db.get_nalog(conn, 99999) is None
db.update_nalog(conn, n2, None, "  kočnice i lanac ", "gotovo")
g = db.get_nalog(conn, n2, today)
assert g["rok"] is None and g["opis_klijent"] == "kočnice i lanac" and g["opis_radova"] == "gotovo" and g["status"] == "otvoren"

# brisanje: samo otvoreni, a broj obrisanog naloga se ne izdaje ponovno
x = db.open_nalog(conn, b1, "za brisanje", today=today)
broj_x = db.get_nalog(conn, x)["broj"]
db.delete_nalog(conn, x)
assert db.get_nalog(conn, x) is None
y = db.open_nalog(conn, b1, "idući", today=today)
assert db.get_nalog(conn, y)["broj"] != broj_x
for bad_id in (n1, n3):                       # n1 je preuzet, n3 preuzet (auto_preuzet)
    try:
        db.delete_nalog(conn, bad_id); assert False
    except ValueError as e:
        assert "otvoreni" in str(e)
try:
    db.delete_nalog(conn, 999999); assert False
except ValueError:
    pass

# integritet: bicikl mora imati klijenta
try:
    conn.execute("INSERT INTO bicikl(klijent_id, naziv) VALUES (999, 'x')"); assert False
except Exception as e:
    assert "FOREIGN KEY" in str(e)

# nova migracija na postojeću bazu pravi backup i čuva podatke
conn.close()
base = len(db.MIGRATIONS)
db.MIGRATIONS.append("ALTER TABLE klijent ADD COLUMN adresa TEXT NOT NULL DEFAULT '';")
conn = db.connect(path)
assert db.schema_version(conn) == base + 1
assert conn.execute("SELECT COUNT(*) FROM klijent").fetchone()[0] == 2
assert any(f.startswith(f"servis_pre_v{base}_") for f in os.listdir(os.path.join(d, "backup")))

# starija aplikacija ne smije dirati noviju bazu
conn.close(); db.MIGRATIONS.pop()
try:
    db.connect(path); assert False
except RuntimeError as e:
    print("OK nova baza/stara app:", str(e)[:50])
# --- korisnici: dodavanje, imena, deaktivacija, lozinka
conn = db.connect(os.path.join(tempfile.mkdtemp(), "k.db"))
s_id = db.list_korisnici(conn)[0]["id"]
for bad in ("", "  ", "serviser", "SERVISER"):
    try:
        db.add_korisnik(conn, bad); assert False, bad
    except ValueError:
        pass
a = db.add_korisnik(conn, "Ana")
db.update_korisnik(conn, s_id, ime="Mehaničar")                    # preimenovanje prvog korisnika
assert [r["ime"] for r in db.list_korisnici(conn)] == ["Mehaničar", "Ana"]
try:
    db.update_korisnik(conn, a, ime="mehanicar"); assert False      # isto ime (bez dijakritika)
except ValueError:
    pass
db.update_korisnik(conn, a, ime="Ana")                              # isto ime sam sebi je OK
db.set_lozinka(conn, a, "tajna")
assert db.check_lozinka(conn, a, "tajna") and not db.check_lozinka(conn, a, "Tajna")
db.set_lozinka(conn, a, "")                                         # uklanjanje lozinke
assert db.check_lozinka(conn, a, "") and not db.get_korisnik(conn, a)["ima_lozinku"]
db.update_korisnik(conn, a, aktivan=False)
assert [r["ime"] for r in db.list_korisnici(conn)] == ["Mehaničar"]
assert len(db.list_korisnici(conn, only_active=False)) == 2
assert not db.check_lozinka(conn, a, "")                            # deaktiviran se ne može prijaviti
try:
    db.update_korisnik(conn, s_id, aktivan=False); assert False     # zadnji aktivni
except ValueError as e:
    assert "barem jedan" in str(e)
assert [r["ime"] for r in db.list_korisnici(conn)] == ["Mehaničar"]

# --- reset lozinki preko datoteke (zaboravljena lozinka)
dd = tempfile.mkdtemp()
db.set_lozinka(conn, s_id, "x")
assert db.reset_lozinke_if_requested(conn, dd) is False and db.get_korisnik(conn, s_id)["ima_lozinku"]
open(os.path.join(dd, db.RESET_FILE), "w").close()
assert db.reset_lozinke_if_requested(conn, dd) is True
assert not db.get_korisnik(conn, s_id)["ima_lozinku"] and not os.path.exists(os.path.join(dd, db.RESET_FILE))
conn.close()

# --- nadogradnja STARE baze (shema 1, kakva je već u servisu) na trenutnu: podaci ostaju, pojavljuje se Serviser
full = list(db.MIGRATIONS)
old_path = os.path.join(tempfile.mkdtemp(), "stara.db")
db.MIGRATIONS[:] = full[:1]
old = db.connect(old_path)
assert db.schema_version(old) == 1 and old.execute("SELECT COUNT(*) FROM korisnik").fetchone()[0] == 0
kk = db.add_klijent(old, "Stari Klijent"); bb = db.add_bicikl(old, kk, "Stari Bicikl")
nn = db.open_nalog(old, bb, "stari opis", today=date(2026, 11, 3))
old.execute("UPDATE nalog SET status='gotov', datum_zavrsetka='2026-11-05', opis_radova='stari rad', zatvorio_korisnik_id=NULL WHERE id=?", (nn,))
old.commit()
old.close()
db.MIGRATIONS[:] = full
new = db.connect(old_path)
assert db.schema_version(new) == len(full)
assert [r["ime"] for r in db.list_korisnici(new)] == ["Serviser"]
g = db.get_nalog(new, nn)
assert g["opis_klijent"] == "stari opis" and g["opis_radova"] == "stari rad" and g["status"] == "gotov"
assert g["otvorio_ime"] is None and g["odradio_ime"] is None and g["predao_ime"] is None   # stari nalozi nemaju korisnika
assert any(f.startswith("servis_pre_v1_") for f in os.listdir(os.path.join(os.path.dirname(old_path), "backup")))
new.close()

print("SVI TESTOVI PROŠLI")
