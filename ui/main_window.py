"""Glavni prozor: pregled naloga (otvoreni / gotovi / preuzeti) s pretragom."""
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QPushButton, QTabBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

import db
from ui import theme
from ui.common import APP_NAME, fmt_date
from ui.dialogs import NalogDialog, NoviNalogDialog, PostavkeDialog
from version import VERSION

TABS = [(db.STATUS_OTVOREN, "Otvoreni"), (db.STATUS_GOTOV, "Gotovi"), (db.STATUS_PREUZET, "Preuzeti")]

# (naslov, ključ, vrsta) - "date" se prikazuje kao 06.11.2026.
COLUMNS = {
    db.STATUS_OTVOREN: [("Nalog", "broj", ""), ("Klijent", "klijent_naziv", ""), ("Telefon", "klijent_telefon", ""),
                        ("Bicikl", "bicikl_naziv", ""), ("Zaprimljeno", "datum_zaprimanja", "date"),
                        ("Rok", "rok", "date"), ("Upozorenje", "upozorenje", "")],
    db.STATUS_GOTOV: [("Nalog", "broj", ""), ("Klijent", "klijent_naziv", ""), ("Telefon", "klijent_telefon", ""),
                      ("Bicikl", "bicikl_naziv", ""), ("Zaprimljeno", "datum_zaprimanja", "date"),
                      ("Završeno", "datum_zavrsetka", "date")],
    db.STATUS_PREUZET: [("Nalog", "broj", ""), ("Klijent", "klijent_naziv", ""), ("Bicikl", "bicikl_naziv", ""),
                        ("Zaprimljeno", "datum_zaprimanja", "date"), ("Završeno", "datum_zavrsetka", "date"),
                        ("Preuzeto", "datum_preuzimanja", "date")],
}
STRETCH_KEYS = {"klijent_naziv", "bicikl_naziv"}   # upozorenje: uvijek cijeli tekst
EMPTY_TEXT = {
    db.STATUS_OTVOREN: "Nema otvorenih naloga.",
    db.STATUS_GOTOV: "Nema gotovih naloga koji čekaju preuzimanje.",
    db.STATUS_PREUZET: "Nema preuzetih naloga.",
}


class MainWindow(QMainWindow):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.data = {s: [] for s, _ in TABS}
        self.setWindowTitle(f"{APP_NAME} {VERSION}")
        self.resize(1100, 650)
        self.setMinimumSize(800, 500)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Traži: klijent, telefon, bicikl ili broj naloga   (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.btn_novi = QPushButton("+ Novi nalog   (Ctrl+N)")
        self.btn_novi.setObjectName("primary")
        self.btn_novi.setAutoDefault(False)
        btn_postavke = QPushButton("Postavke")
        btn_postavke.setAutoDefault(False)

        top = QHBoxLayout()
        top.addWidget(self.search, 1)
        top.addWidget(self.btn_novi)
        top.addWidget(btn_postavke)

        self.tabs = QTabBar()
        self.tabs.setExpanding(False)
        for _, title in TABS:
            self.tabs.addTab(title)

        self.table = QTableWidget()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.horizontalHeader().setHighlightSections(False)

        self.empty = QLabel("")
        self.empty.setObjectName("hint")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status = QLabel("Dvoklik ili Enter na nalogu otvara detalje.")
        self.status.setObjectName("hint")

        box = QVBoxLayout()
        box.addLayout(top)
        box.addSpacing(6)
        box.addWidget(self.tabs)
        box.addWidget(self.table, 1)
        box.addWidget(self.empty)
        box.addWidget(self.status)
        central = QWidget()
        central.setLayout(box)
        self.setCentralWidget(central)

        self.search.textChanged.connect(self._render)
        self.tabs.currentChanged.connect(self._render)
        self.btn_novi.clicked.connect(self.novi_nalog)
        btn_postavke.clicked.connect(self.postavke)
        self.table.cellDoubleClicked.connect(lambda row, _c: self._open_row(row))
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.novi_nalog)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=lambda: (self.search.setFocus(), self.search.selectAll()))
        QShortcut(QKeySequence("Return"), self.table, activated=lambda: self._open_row(self.table.currentRow()))
        QShortcut(QKeySequence("Escape"), self, activated=self.search.clear)

        # datumi se mijenjaju preko noći i drugi put netko drugi unese nalog: osvježi svake minute
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(60_000)

        self.refresh()

    # --- podaci
    def refresh(self):
        self.data[db.STATUS_OTVOREN] = db.sort_by_urgency(db.list_nalozi(self.conn, db.STATUS_OTVOREN))
        self.data[db.STATUS_GOTOV] = sorted(db.list_nalozi(self.conn, db.STATUS_GOTOV),
                                            key=lambda d: d["datum_zavrsetka"] or "")
        self.data[db.STATUS_PREUZET] = sorted(db.list_nalozi(self.conn, db.STATUS_PREUZET),
                                              key=lambda d: d["datum_preuzimanja"] or "", reverse=True)
        for i, (status, title) in enumerate(TABS):
            self.tabs.setTabText(i, f"{title} ({len(self.data[status])})")
        self._render()

    def _matches(self, d, words):
        text = db.normalize(f"{d['klijent_naziv']} {d['bicikl_naziv']} {d['broj']} {d['klijent_telefon']}")
        compact = text.replace(" ", "")  # da "0911234567" nađe "091 123 4567"
        return all(w in text or w in compact for w in words)

    def _render(self, *_):
        status = TABS[self.tabs.currentIndex()][0]
        words = db.normalize(self.search.text()).split()
        rows = [d for d in self.data[status] if self._matches(d, words)]
        cols = COLUMNS[status]

        self.table.setUpdatesEnabled(False)
        self.table.clear()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels([c[0] for c in cols])
        self.table.setRowCount(len(rows))
        bg_fg = {"crvena": (theme.RED_BG, theme.RED_FG), "zuta": (theme.AMBER_BG, theme.AMBER_FG)}
        for r, d in enumerate(rows):
            colors = bg_fg.get(d.get("boja", ""))
            for c, (_, key, kind) in enumerate(cols):
                value = d.get(key) or ""
                item = QTableWidgetItem(fmt_date(value) if kind == "date" else str(value))
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, d["id"])
                if colors:
                    item.setBackground(QBrush(QColor(colors[0])))
                    item.setForeground(QBrush(QColor(colors[1])))
                if key == "upozorenje" and value:
                    f = item.font(); f.setBold(True); item.setFont(f)
                self.table.setItem(r, c, item)
        header = self.table.horizontalHeader()
        for c, (_, key, _) in enumerate(cols):
            header.setSectionResizeMode(c, QHeaderView.ResizeMode.Stretch if key in STRETCH_KEYS
                                        else QHeaderView.ResizeMode.ResizeToContents)
        self.table.setUpdatesEnabled(True)
        # namjerno BEZ automatskog označavanja prvog retka: označeni redak je plav i krije crveno/žuto isticanje

        total = len(self.data[status])
        if not rows:
            self.empty.setText(EMPTY_TEXT[status] if not words and total == 0
                               else f"Nema rezultata za „{self.search.text().strip()}” u ovom popisu"
                                    + (" - pogledaj druge kartice." if any(self.data[s] for s, _ in TABS if s != status) else "."))
            self.empty.show()
        else:
            self.empty.hide()

    # --- akcije
    def _open_row(self, row):
        if row < 0 or self.table.item(row, 0) is None:
            return
        nalog_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if NalogDialog(self.conn, nalog_id, self).exec():
            self.refresh()

    def novi_nalog(self):
        dlg = NoviNalogDialog(self.conn, self, start_text=self.search.text().strip())
        if dlg.exec():
            self.search.clear()
            self.tabs.setCurrentIndex(0)
            self.refresh()
            n = db.get_nalog(self.conn, dlg.nalog_id)
            self.status.setText(f"Otvoren nalog {n['broj']}: {n['klijent_naziv']}, {n['bicikl_naziv']}.")

    def postavke(self):
        if PostavkeDialog(self.conn, self).exec():
            self.refresh()
