"""Testira ekrane kroz kod (bez miša): python test_ui.py   (radi i bez ekrana, offscreen)"""
import os
import sys
import tempfile
from datetime import date, timedelta

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SERVIS_DATA_DIR"] = tempfile.mkdtemp()

from PyQt6.QtWidgets import QApplication

import db
from ui import theme
from ui.dialogs import KorisnikDialog, LoginDialog, NalogDialog, NoviNalogDialog, PostavkeDialog
from ui.common import APP_NAME
from ui.main_window import MainWindow
from version import VERSION

app = QApplication(sys.argv)
app.setStyleSheet(theme.STYLESHEET)
conn = db.connect()
w = MainWindow(conn)
w.show()
assert w.table.rowCount() == 0 and "Nema otvorenih" in w.empty.text()
assert w.tabs.tabText(0) == "Otvoreni (0)"

# --- novi klijent + novi bicikl -> nalog
dlg = NoviNalogDialog(conn, w, start_text="Čorić Marija")
dlg._start_novi_klijent()
dlg.novi_telefon.setText("091 123 4567")
dlg.bicikl_novi.setText("Trek Marlin")
dlg.opis.setPlainText("Cuje lanac")
rok = date.today() + timedelta(days=1)
dlg.rok_check.setChecked(True)
dlg.rok_edit.setDate(dlg.rok_edit.date().fromString(rok.isoformat(), "yyyy-MM-dd"))
dlg._submit()
assert dlg.nalog_id and dlg.result() == 1
w.refresh()
assert w.table.rowCount() == 1 and w.table.item(0, 1).text() == "Čorić Marija"
assert w.table.item(0, 6).text() == "Rok za 1 dan"          # žuto upozorenje
assert w.tabs.tabText(0) == "Otvoreni (1)"

# --- validacije: bez klijenta / bez bicikla se ne otvara nalog
d2 = NoviNalogDialog(conn, w)
d2._submit(); assert d2.nalog_id is None and "klijenta" in d2.error.text()
d2.search.setText("coric"); app.processEvents()
assert d2.klijent_id is not None                              # jedan rezultat se sam odabere
assert d2.bicikl_combo.count() == 1 and d2.bicikl_combo.currentText() == "Trek Marlin"
d2.opis.setPlainText("Zamjena guma")
d2._submit()                                                  # postojeći bicikl iz izbornika
assert d2.nalog_id and len(db.bicikli_klijenta(conn, d2.klijent_id)) == 1
d3 = NoviNalogDialog(conn, w, start_text="Nepoznat")
assert d3.results.count() == 0 and "Nema klijenta" in d3.hint.text()
d3._start_novi_klijent(); d3.novi_naziv.setText("")
d3._submit(); assert d3.nalog_id is None and "ime klijenta" in d3.error.text()
d3._start_novi_klijent()                                      # drugi klik: natrag na pretragu
assert not d3.novi_klijent and not d3.search.isHidden()
d3.reject()

# --- pretraga na pregledu
w.refresh(); assert w.table.rowCount() == 2
w.search.setText("0911234567"); assert w.table.rowCount() == 2
w.search.setText("marlin"); assert w.table.rowCount() == 2
w.search.setText("xyz"); assert w.table.rowCount() == 0 and "Nema rezultata" in w.empty.text()
w.search.clear(); assert w.table.rowCount() == 2

# --- završi nalog: bez opisa radova ne ide; s opisom ide u Gotove
first = w.table.item(0, 0).data(0x0100)
nd = NalogDialog(conn, first)
nd._finish()
assert "napravljeno" in nd.error.text() and db.get_nalog(conn, first)["status"] == "otvoren"
nd.opis_radova.setPlainText("Zamijenjen lanac")
nd._finish()
assert db.get_nalog(conn, first)["status"] == "gotov"
w.refresh()
assert w.tabs.tabText(0) == "Otvoreni (1)" and w.tabs.tabText(1) == "Gotovi (1)"

# --- označi kao preuzet
nd = NalogDialog(conn, first)
nd._preuzet()
assert db.get_nalog(conn, first)["status"] == "preuzet"
w.refresh(); assert w.tabs.tabText(2) == "Preuzeti (1)"
nd = NalogDialog(conn, first)                                 # preuzet je samo za pregled
assert not nd.opis_radova.isEnabled()

# --- spremanje izmjene roka i opisa na otvorenom nalogu
open_id = db.list_nalozi(conn, "otvoren")[0]["id"]
nd = NalogDialog(conn, open_id)
nd.rok_check.setChecked(False); nd.opis_klijent.setPlainText("izmijenjeno")
nd._save_close()
g = db.get_nalog(conn, open_id); assert g["rok"] is None and g["opis_klijent"] == "izmijenjeno"

# --- postavke utječu na isticanje i na završetak
pd = PostavkeDialog(conn); pd.n.setValue(1); pd.auto.setChecked(True); pd._save()
assert db.get_setting(conn, "dana_u_servisu") == "1" and db.get_setting(conn, "auto_preuzet") == "1"
db.finish_nalog(conn, open_id, "gotovo")
assert db.get_nalog(conn, open_id)["status"] == "preuzet"     # auto_preuzet preskače "gotov"

# --- brisanje kroz sučelje: pitanje "jeste li sigurni", Ne ne briše, Da briše; gotovi nemaju gumb
from PyQt6.QtWidgets import QPushButton
db.set_setting(conn, "auto_preuzet", 0)
k = db.add_klijent(conn, "Za Brisanje"); b = db.add_bicikl(conn, k, "Bicikl")
nid = db.open_nalog(conn, b, "greška u unosu")
w.refresh()
assert w.windowTitle() == f"{APP_NAME} {VERSION}" and APP_NAME == "Servis bicikala Gema"
nd = NalogDialog(conn, nid)
assert any(bt.text() == "Obriši nalog" for bt in nd.findChildren(QPushButton))
nd._confirm_delete = lambda: False
nd._delete(); assert db.get_nalog(conn, nid) is not None            # "Ne" ne briše
nd._confirm_delete = lambda: True
nd._delete(); assert db.get_nalog(conn, nid) is None and nd.result() == 1
db.open_nalog(conn, b, "x"); g_id = db.list_nalozi(conn, "otvoren")[-1]["id"]
db.finish_nalog(conn, g_id, "gotovo")                               # gotov nalog: nema gumba za brisanje
gd = NalogDialog(conn, g_id)
assert not any(bt.text() == "Obriši nalog" for bt in gd.findChildren(QPushButton))

# =================== korisnici i prijava ===================
conn2 = db.connect(os.path.join(tempfile.mkdtemp(), "login.db"))
serviser = db.list_korisnici(conn2)[0]["id"]

# prvi korisnik je ponuđen, nema polja za lozinku, Prijava radi bez nje
ld = LoginDialog(conn2)
assert ld.combo.count() == 1 and ld.combo.currentText() == "Serviser" and ld.lozinka.isHidden()
ld._login()
assert ld.korisnik_id == serviser and ld.ime == "Serviser" and ld.result() == 1

# novi korisnik s lozinkom kroz dijalog: lozinke se moraju podudarati, ime ne smije biti zauzeto
kd = KorisnikDialog(conn2)
kd.ime.setText("Ana"); kd.lozinka.setText("tajna"); kd.ponovi.setText("druga")
kd._save(); assert "podudaraju" in kd.error.text() and kd.result() == 0
kd.ponovi.setText("tajna"); kd.ime.setText("serviser")
kd._save(); assert "već postoji" in kd.error.text() and kd.result() == 0
kd.ime.setText("Ana"); kd._save()
assert kd.result() == 1
ana = [r["id"] for r in db.list_korisnici(conn2) if r["ime"] == "Ana"][0]

# prijava s lozinkom: polje se pojavi samo za korisnika koji je ima; kriva lozinka ne prolazi
ld = LoginDialog(conn2)
assert ld.combo.currentText() == "Serviser" and ld.lozinka.isHidden()      # zadnji prijavljeni (Serviser)
ld.combo.setCurrentIndex(ld.combo.findText("Ana"))
assert not ld.lozinka.isHidden()
ld.lozinka.setText("kriva"); ld._login()
assert ld.korisnik_id is None and "Pogrešna" in ld.error.text() and ld.lozinka.text() == ""
ld.lozinka.setText("tajna"); ld._login()
assert ld.korisnik_id == ana and ld.result() == 1
assert db.get_setting(conn2, "zadnji_korisnik") == str(ana)
ld2 = LoginDialog(conn2)                                                    # sljedeći put je predodabrana Ana
assert ld2.combo.currentText() == "Ana" and not ld2.lozinka.isHidden()

# uređivanje: ukloni lozinku, promjena imena, deaktivacija zadnjeg aktivnog se odbija
kd = KorisnikDialog(conn2, ana); kd.ukloni.setChecked(True); kd.ime.setText("Ana M."); kd._save()
assert db.get_korisnik(conn2, ana)["ime"] == "Ana M." and not db.get_korisnik(conn2, ana)["ima_lozinku"]
db.update_korisnik(conn2, serviser, aktivan=False)
kd = KorisnikDialog(conn2, ana); kd.aktivan.setChecked(False); kd._save()
assert "barem jedan" in kd.error.text() and db.get_korisnik(conn2, ana)["aktivan"] == 1
db.update_korisnik(conn2, serviser, aktivan=True)

# --- tri korisnika na nalogu kroz sučelje: otvorio (Serviser), odradio (Ana, izabran u izborniku), predao (Serviser)
w2 = MainWindow(conn2, serviser)
assert "Serviser" in w2.user_label.text()
nk = db.add_klijent(conn2, "Klijent"); nb = db.add_bicikl(conn2, nk, "Bicikl")
nd = NoviNalogDialog(conn2, w2, korisnik_id=serviser)
nd.search.setText("klijent"); nd.opis.setPlainText("x"); nd._submit()
assert db.get_nalog(conn2, nd.nalog_id)["otvorio_ime"] == "Serviser"
dd = NalogDialog(conn2, nd.nalog_id, w2, korisnik_id=serviser)
assert dd.odradio_combo.currentText() == "Serviser"                          # predodabran prijavljeni
dd.odradio_combo.setCurrentIndex(dd.odradio_combo.findText("Ana M."))
dd.opis_radova.setPlainText("servis gotov"); dd._finish()
g = db.get_nalog(conn2, nd.nalog_id)
assert (g["otvorio_ime"], g["odradio_ime"], g["predao_ime"]) == ("Serviser", "Ana M.", None) and g["status"] == "gotov"
dd = NalogDialog(conn2, nd.nalog_id, w2, korisnik_id=serviser)
assert dd.odradio_combo is None                                              # gotov: odradio je samo prikaz
dd._preuzet()
g = db.get_nalog(conn2, nd.nalog_id)
assert (g["odradio_ime"], g["predao_ime"]) == ("Ana M.", "Serviser") and g["status"] == "preuzet"

# auto_preuzet: predao = odradio
db.set_setting(conn2, "auto_preuzet", 1)
nd2 = NoviNalogDialog(conn2, w2, korisnik_id=serviser); nd2.search.setText("klijent"); nd2._submit()
dd = NalogDialog(conn2, nd2.nalog_id, w2, korisnik_id=serviser)
dd.odradio_combo.setCurrentIndex(dd.odradio_combo.findText("Ana M.")); dd.opis_radova.setPlainText("ok"); dd._finish()
g = db.get_nalog(conn2, nd2.nalog_id); assert g["odradio_ime"] == g["predao_ime"] == "Ana M."

# --- promjena korisnika u glavnom prozoru (LoginDialog.exec zamijenjen odabirom Ane)
orig_exec = LoginDialog.exec
def fake_exec(self):
    self.combo.setCurrentIndex(self.combo.findData(ana)); self._login(); return 1
LoginDialog.exec = fake_exec
w2.promijeni_korisnika()
assert w2.korisnik_id == ana and "Ana M." in w2.user_label.text()
# deaktiviranje prijavljenog korisnika u postavkama traži novu prijavu
db.update_korisnik(conn2, ana, aktivan=False)
called = []
w2.promijeni_korisnika = lambda forced=False: called.append(forced)
w2._reload_user(); assert called == [True]
LoginDialog.exec = orig_exec

# --- tablica korisnika u postavkama
pd2 = PostavkeDialog(conn2)
assert pd2.users.rowCount() == 2
imena = [pd2.users.item(r, 0).text() for r in range(2)]
statusi = [pd2.users.item(r, 2).text() for r in range(2)]
assert imena == ["Serviser", "Ana M."] and statusi == ["aktivan", "neaktivan"]

print("SVI TESTOVI PROŠLI (test_ui)")
