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
from ui.dialogs import NalogDialog, NoviNalogDialog, PostavkeDialog
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

print("SVI TESTOVI PROŠLI (test_ui)")
