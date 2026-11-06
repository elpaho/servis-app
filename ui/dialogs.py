"""Dijalozi: novi nalog, detalji naloga, postavke."""
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QVBoxLayout,
)

import db
from ui.common import STATUS_LABEL, fmt_date

DATE_FORMAT = "dd.MM.yyyy."


def _iso(qdate: QDate) -> str:
    return qdate.toString("yyyy-MM-dd")


def _rok_widgets(initial_iso=None, default_days=3):
    """Kvačica 'Dogovoren rok' + izbornik datuma (aktivan samo kad je kvačica uključena)."""
    check = QCheckBox("Dogovoren rok")
    edit = QDateEdit()
    edit.setCalendarPopup(True)
    edit.setDisplayFormat(DATE_FORMAT)
    if initial_iso:
        edit.setDate(QDate.fromString(initial_iso, "yyyy-MM-dd"))
        check.setChecked(True)
    else:
        edit.setDate(QDate.currentDate().addDays(default_days))
    edit.setEnabled(check.isChecked())
    check.toggled.connect(edit.setEnabled)
    return check, edit


def _text_edit(placeholder="", height=90):
    w = QPlainTextEdit()
    w.setPlaceholderText(placeholder)
    w.setFixedHeight(height)
    w.setTabChangesFocus(True)
    return w


class NoviNalogDialog(QDialog):
    """Klijent (traži ili novi) -> bicikl (izaberi ili novi) -> opis i rok -> otvori nalog."""

    def __init__(self, conn, parent=None, start_text=""):
        super().__init__(parent)
        self.conn = conn
        self.nalog_id = None
        self.klijent_id = None
        self.novi_klijent = False
        self.setWindowTitle("Novi nalog")
        self.setMinimumWidth(560)

        # --- klijent
        self.search = QLineEdit(start_text)
        self.search.setPlaceholderText("Traži klijenta po imenu ili telefonu")
        self.results = QListWidget()
        self.results.setFixedHeight(130)
        self.hint = QLabel("")
        self.hint.setObjectName("hint")
        self.btn_novi_klijent = QPushButton("+ Novi klijent")
        self.novi_naziv = QLineEdit()
        self.novi_naziv.setPlaceholderText("Ime i prezime ili naziv firme")
        self.novi_telefon = QLineEdit()
        self.novi_telefon.setPlaceholderText("Telefon (nije obavezno)")
        self.odabrani = QLabel("")
        self.odabrani.setStyleSheet("font-weight: 600;")

        self.box_klijent = QGroupBox("Klijent")
        kl = QVBoxLayout(self.box_klijent)
        kl.addWidget(self.search)
        kl.addWidget(self.results)
        row = QHBoxLayout()
        row.addWidget(self.hint, 1)
        row.addWidget(self.btn_novi_klijent)
        kl.addLayout(row)
        kl.addWidget(self.novi_naziv)
        kl.addWidget(self.novi_telefon)
        kl.addWidget(self.odabrani)

        # --- bicikl
        self.bicikl_combo = QComboBox()
        self.bicikl_novi = QLineEdit()
        self.bicikl_novi.setPlaceholderText("ili upiši novi bicikl, npr. Trek Marlin 7")
        box_b = QGroupBox("Bicikl")
        bl = QVBoxLayout(box_b)
        bl.addWidget(self.bicikl_combo)
        bl.addWidget(self.bicikl_novi)

        # --- nalog
        self.opis = _text_edit("Što je rekao klijent, što treba napraviti")
        self.rok_check, self.rok_edit = _rok_widgets()
        box_n = QGroupBox("Nalog")
        nl = QVBoxLayout(box_n)
        nl.addWidget(self.opis)
        r = QHBoxLayout()
        r.addWidget(self.rok_check)
        r.addWidget(self.rok_edit)
        r.addStretch()
        nl.addLayout(r)

        self.error = QLabel("")
        self.error.setObjectName("error")
        self.btn_ok = QPushButton("Otvori nalog")
        self.btn_ok.setObjectName("primary")
        self.btn_ok.setDefault(True)
        btn_cancel = QPushButton("Odustani")
        btn_cancel.setAutoDefault(False)
        self.btn_novi_klijent.setAutoDefault(False)
        buttons = QHBoxLayout()
        buttons.addWidget(self.error, 1)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(self.btn_ok)

        main = QVBoxLayout(self)
        main.addWidget(self.box_klijent)
        main.addWidget(box_b)
        main.addWidget(box_n)
        main.addLayout(buttons)

        self.search.textChanged.connect(self._search_changed)
        self.search.returnPressed.connect(self._enter_in_search)
        self.results.itemClicked.connect(self._pick_klijent)
        self.results.itemActivated.connect(self._pick_klijent)
        self.btn_novi_klijent.clicked.connect(self._start_novi_klijent)
        self.btn_ok.clicked.connect(self._submit)
        btn_cancel.clicked.connect(self.reject)

        self._set_mode_search()
        self._search_changed(self.search.text())
        self.search.setFocus()

    # --- stanja
    def _set_mode_search(self):
        self.novi_klijent = False
        self.novi_naziv.hide()
        self.novi_telefon.hide()
        self.search.show()
        self.results.show()
        self.btn_novi_klijent.setText("+ Novi klijent")
        self.btn_novi_klijent.show()
        self.hint.show()

    def _search_changed(self, text):
        if self.novi_klijent:
            return
        self.klijent_id = None
        self.odabrani.setText("")
        self._fill_bicikli([])
        self.results.clear()
        if not text.strip():
            self.hint.setText("Upiši dio imena ili telefona.")
            return
        found = db.search_klijenti(self.conn, text)
        for k in found:
            label = k["naziv"] + (f"   ·   {k['telefon']}" if k["telefon"] else "")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, k["id"])
            self.results.addItem(item)
        self.hint.setText("" if found else f"Nema klijenta „{text.strip()}”. Klikni + Novi klijent.")
        if len(found) == 1:
            self.results.setCurrentRow(0)
            self._pick_klijent(self.results.item(0))

    def _enter_in_search(self):
        """Enter u pretrazi: izaberi prvog u popisu i skoči na bicikl."""
        if self.klijent_id is None and self.results.count():
            self.results.setCurrentRow(0)
            self._pick_klijent(self.results.item(0))
        if self.klijent_id is not None:
            (self.bicikl_combo if self.bicikl_combo.count() else self.bicikl_novi).setFocus()

    def _pick_klijent(self, item):
        self.klijent_id = item.data(Qt.ItemDataRole.UserRole)
        self.odabrani.setText(f"Odabran: {item.text().split('   ·')[0]}")
        self._fill_bicikli(db.bicikli_klijenta(self.conn, self.klijent_id))

    def _fill_bicikli(self, rows):
        self.bicikl_combo.clear()
        for b in rows:
            self.bicikl_combo.addItem(b["naziv"], b["id"])
        self.bicikl_combo.setVisible(bool(rows))
        if rows:
            self.bicikl_novi.setPlaceholderText("ili upiši novi bicikl")
        else:
            self.bicikl_novi.setPlaceholderText("Bicikl, npr. Trek Marlin 7")

    def _start_novi_klijent(self):
        if self.novi_klijent:           # drugi klik = povratak na pretragu
            self._set_mode_search()
            self._search_changed(self.search.text())
            return
        self.novi_klijent = True
        self.klijent_id = None
        self.novi_naziv.setText(self.search.text().strip())
        self.search.hide()
        self.results.hide()
        self.odabrani.setText("")
        self.hint.setText("Novi klijent:")
        self.btn_novi_klijent.setText("Natrag na pretragu")
        self.novi_naziv.show()
        self.novi_telefon.show()
        self._fill_bicikli([])
        self.novi_naziv.setFocus()

    # --- spremanje
    def _submit(self):
        naziv_bicikla = self.bicikl_novi.text().strip()
        if self.novi_klijent:
            if not self.novi_naziv.text().strip():
                return self._err("Upiši ime klijenta.")
        elif self.klijent_id is None:
            return self._err("Izaberi klijenta s popisa ili klikni + Novi klijent.")
        if not naziv_bicikla and not (self.bicikl_combo.count() and self.bicikl_combo.currentData()):
            return self._err("Upiši bicikl.")

        klijent_id = self.klijent_id
        if self.novi_klijent:
            klijent_id = db.add_klijent(self.conn, self.novi_naziv.text(), telefon=self.novi_telefon.text())
        bicikl_id = db.add_bicikl(self.conn, klijent_id, naziv_bicikla) if naziv_bicikla else self.bicikl_combo.currentData()
        rok = _iso(self.rok_edit.date()) if self.rok_check.isChecked() else None
        self.nalog_id = db.open_nalog(self.conn, bicikl_id, self.opis.toPlainText(), rok=rok)
        self.accept()

    def _err(self, text):
        self.error.setText(text)


class NalogDialog(QDialog):
    """Detalji naloga. Otvoren: uredi i završi. Gotov: označi preuzet. Preuzet: samo pregled."""

    def __init__(self, conn, nalog_id, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.nalog_id = nalog_id
        n = db.get_nalog(conn, nalog_id)
        self.status = n["status"]
        self.broj, self.klijent, self.bicikl = n["broj"], n["klijent_naziv"], n["bicikl_naziv"]
        self.setWindowTitle(f"Nalog {n['broj']}")
        self.setMinimumWidth(560)
        editable = self.status != db.STATUS_PREUZET

        head = QLabel(f"<span style='font-size:15pt; font-weight:600'>{n['broj']}</span>"
                      f"&nbsp;&nbsp;<span style='color:#5f5e5a'>{STATUS_LABEL[self.status]}</span>")
        info = QFormLayout()
        info.addRow("Klijent:", QLabel(n["klijent_naziv"] + (f"   ·   {n['klijent_telefon']}" if n["klijent_telefon"] else "")))
        info.addRow("Bicikl:", QLabel(n["bicikl_naziv"]))
        info.addRow("Zaprimljeno:", QLabel(f"{fmt_date(n['datum_zaprimanja'])}   ({n['dana_u_servisu']} dana)"))
        if n["datum_zavrsetka"]:
            info.addRow("Završeno:", QLabel(fmt_date(n["datum_zavrsetka"])))
        if n["datum_preuzimanja"]:
            info.addRow("Preuzeto:", QLabel(fmt_date(n["datum_preuzimanja"])))
        self.warning = QLabel(n["upozorenje"])
        if n["upozorenje"]:
            self.warning.setStyleSheet("color: #A32D2D; font-weight: 600;")
            info.addRow("Upozorenje:", self.warning)

        self.rok_check, self.rok_edit = _rok_widgets(n["rok"])
        rok_row = QHBoxLayout()
        rok_row.addWidget(self.rok_check)
        rok_row.addWidget(self.rok_edit)
        rok_row.addStretch()
        self.opis_klijent = _text_edit()
        self.opis_klijent.setPlainText(n["opis_klijent"])
        self.opis_radova = _text_edit("Upiši što je stvarno napravljeno" if self.status == db.STATUS_OTVOREN else "")
        self.opis_radova.setPlainText(n["opis_radova"])
        if not editable:
            for w in (self.rok_check, self.rok_edit, self.opis_klijent, self.opis_radova):
                w.setEnabled(False)

        self.error = QLabel("")
        self.error.setObjectName("error")
        btn_close = QPushButton("Zatvori" if not editable else "Odustani")
        btn_close.setAutoDefault(False)
        btn_close.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        if self.status == db.STATUS_OTVOREN:
            btn_delete = QPushButton("Obriši nalog")
            btn_delete.setAutoDefault(False)
            btn_delete.setStyleSheet("color: #A32D2D;")
            btn_delete.clicked.connect(self._delete)
            buttons.addWidget(btn_delete)
        buttons.addWidget(self.error, 1)
        buttons.addWidget(btn_close)
        if editable:
            btn_save = QPushButton("Spremi")
            btn_save.setAutoDefault(False)
            btn_save.clicked.connect(self._save_close)
            buttons.addWidget(btn_save)
            action = QPushButton("Završi nalog" if self.status == db.STATUS_OTVOREN else "Označi kao preuzet")
            action.setObjectName("primary")
            action.clicked.connect(self._finish if self.status == db.STATUS_OTVOREN else self._preuzet)
            buttons.addWidget(action)

        main = QVBoxLayout(self)
        main.addWidget(head)
        main.addLayout(info)
        main.addLayout(rok_row)
        g1 = QGroupBox("Što je rekao klijent")
        QVBoxLayout(g1).addWidget(self.opis_klijent)
        g2 = QGroupBox("Što je napravljeno")
        QVBoxLayout(g2).addWidget(self.opis_radova)
        main.addWidget(g1)
        main.addWidget(g2)
        main.addLayout(buttons)

    def _save(self):
        rok = _iso(self.rok_edit.date()) if self.rok_check.isChecked() else None
        db.update_nalog(self.conn, self.nalog_id, rok, self.opis_klijent.toPlainText(), self.opis_radova.toPlainText())

    def _save_close(self):
        self._save()
        self.accept()

    def _confirm_delete(self) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Brisanje naloga")
        box.setText(f"Obrisati nalog {self.broj}?")
        box.setInformativeText(f"{self.klijent}, {self.bicikl}\n\nOvo se ne može poništiti.")
        yes = box.addButton("Da, obriši", QMessageBox.ButtonRole.DestructiveRole)
        no = box.addButton("Ne, odustani", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(no)
        box.setEscapeButton(no)
        box.exec()
        return box.clickedButton() is yes

    def _delete(self):
        if not self._confirm_delete():
            return
        db.delete_nalog(self.conn, self.nalog_id)
        self.accept()

    def _finish(self):
        if not self.opis_radova.toPlainText().strip():
            self.error.setText("Upiši što je napravljeno.")
            return
        self._save()
        db.finish_nalog(self.conn, self.nalog_id, self.opis_radova.toPlainText())
        self.accept()

    def _preuzet(self):
        self._save()
        db.mark_preuzet(self.conn, self.nalog_id)
        self.accept()


class PostavkeDialog(QDialog):
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle("Postavke")
        self.setMinimumWidth(480)
        self.n = QSpinBox(); self.n.setRange(1, 90); self.n.setSuffix(" dana")
        self.m = QSpinBox(); self.m.setRange(0, 30); self.m.setSuffix(" dana")
        self.n.setValue(int(db.get_setting(conn, "dana_u_servisu")))
        self.m.setValue(int(db.get_setting(conn, "dana_do_roka")))
        self.auto = QCheckBox("Nalog se pri završetku odmah označi kao preuzet")
        self.auto.setChecked(db.get_setting(conn, "auto_preuzet") == "1")
        form = QFormLayout()
        form.addRow("Crveno ako je u servisu:", self.n)
        form.addRow("Žuto ako rok ističe za:", self.m)
        form.addRow("", self.auto)
        ok = QPushButton("Spremi"); ok.setObjectName("primary"); ok.clicked.connect(self._save)
        cancel = QPushButton("Odustani"); cancel.setAutoDefault(False); cancel.clicked.connect(self.reject)
        row = QHBoxLayout(); row.addStretch(); row.addWidget(cancel); row.addWidget(ok)
        main = QVBoxLayout(self); main.addLayout(form); main.addLayout(row)

    def _save(self):
        db.set_setting(self.conn, "dana_u_servisu", self.n.value())
        db.set_setting(self.conn, "dana_do_roka", self.m.value())
        db.set_setting(self.conn, "auto_preuzet", 1 if self.auto.isChecked() else 0)
        self.accept()
