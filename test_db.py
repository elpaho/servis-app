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
u = db.add_korisnik(conn, "Marko", "1234")
assert db.check_pin(conn, u, "1234") and not db.check_pin(conn, u, "0000")

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
assert out[1] == ("2026-0002", "Kasni 1 dan(a) · 9 dana u servisu")  # crveno
assert out[2] == ("2026-0001", "Rok za 1 dan(a)")              # žuto
assert out[3] == ("2026-0003", "")
assert [r["boja"] for r in rows] == ["crvena", "crvena", "zuta", ""]

# završetak + preuzimanje, ručno
db.finish_nalog(conn, n1, "zamijenjen lanac", korisnik_id=u, today=today)
r = conn.execute("SELECT status, datum_preuzimanja FROM nalog WHERE id=?", (n1,)).fetchone()
assert (r[0], r[1]) == ("gotov", None)
db.mark_preuzet(conn, n1, today)
assert conn.execute("SELECT status FROM nalog WHERE id=?", (n1,)).fetchone()[0] == "preuzet"

# auto_preuzet
db.set_setting(conn, "auto_preuzet", 1)
db.finish_nalog(conn, n3, "gume", today=today)
assert conn.execute("SELECT status FROM nalog WHERE id=?", (n3,)).fetchone()[0] == "preuzet"

# integritet: bicikl mora imati klijenta
try:
    conn.execute("INSERT INTO bicikl(klijent_id, naziv) VALUES (999, 'x')"); assert False
except Exception as e:
    assert "FOREIGN KEY" in str(e)

# nova migracija na postojeću bazu pravi backup i čuva podatke
conn.close()
db.MIGRATIONS.append("ALTER TABLE klijent ADD COLUMN adresa TEXT NOT NULL DEFAULT '';")
conn = db.connect(path)
assert db.schema_version(conn) == 2
assert conn.execute("SELECT COUNT(*) FROM klijent").fetchone()[0] == 2
assert any(f.startswith("servis_pre_v1_") for f in os.listdir(os.path.join(d, "backup")))

# starija aplikacija ne smije dirati noviju bazu
conn.close(); db.MIGRATIONS.pop()
try:
    db.connect(path); assert False
except RuntimeError as e:
    print("OK nova baza/stara app:", str(e)[:50])
print("SVI TESTOVI PROŠLI")
