# nuitka-project: --standalone
# nuitka-project: --enable-plugin=pyqt6
# nuitka-project: --output-filename=servis.exe
# nuitka-project: --include-data-files=cacert.pem=cacert.pem
#
# Konzola (--windows-console-mode) se NE zadaje ovdje nego u build.py:
# disable za release, force za "python build.py --debug-console".
#
# cacert.pem: Nuitkin --include-package-data=certifi ima poznat bug (duplicate
# data file), pa nosimo vlastitu kopiju kao obični data file i registriramo je
# za requests prije bilo kakvog mrežnog poziva. build.py je sam kopira iz certifi.

import os
import sys

import paths

if paths.IS_COMPILED:
    _bundled_cacert = os.path.join(paths.version_dir(), "cacert.pem")
    if os.path.isfile(_bundled_cacert):
        os.environ["SSL_CERT_FILE"] = _bundled_cacert
        os.environ["REQUESTS_CA_BUNDLE"] = _bundled_cacert

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QProgressDialog, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt

import db
from version import VERSION


class MainWindow(QMainWindow):
    """PRIVREMENI kostur: pokazuje da baza i verzija rade. Pravi ekrani dolaze kasnije."""

    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle(f"Servis {VERSION}")
        self.resize(900, 600)
        box = QVBoxLayout()
        box.addWidget(QLabel(f"Servis {VERSION}"))
        otvoreni = len(db.list_nalozi(conn, db.STATUS_OTVOREN))
        box.addWidget(QLabel(f"Otvorenih naloga: {otvoreni}"))
        box.addWidget(QLabel(f"Podaci: {db.get_data_dir()}"))
        box.addStretch()
        central = QWidget()
        central.setLayout(box)
        self.setCentralWidget(central)


def main():
    app = QApplication(sys.argv)
    conn = db.connect()
    window = MainWindow(conn)

    if paths.IS_COMPILED:
        # update i čišćenje starih verzija samo u kompajliranoj aplikaciji, nikad u razvoju
        from updater import UpdateChecker, UpdateWorker, cleanup_in_background
        cleanup_in_background()
        _start_update_check(app, window)

    window.show()
    sys.exit(app.exec())


def _start_update_check(app, window):
    from updater import UpdateChecker, UpdateWorker

    checker = UpdateChecker()
    window._checker = checker  # referenca da je GC ne pokupi

    def on_update_available(remote_version: str):
        print(f"[update] verzija {remote_version} je dostupna, skidam...")
        _download_update(window, checker, remote_version)

    checker.update_available.connect(on_update_available)
    checker.no_update.connect(lambda: print(f"[update] Već na zadnjoj verziji ({VERSION})."))
    checker.check_failed.connect(lambda msg: print(f"[update] Provjera nije uspjela: {msg}"))

    worker = UpdateWorker(checker, mode="check")
    window._check_worker = worker
    worker.start()


def _download_update(window, checker, remote_version: str):
    from updater import UpdateWorker, apply_update_and_restart

    progress = QProgressDialog("Skidam novu verziju...", None, 0, 100, window)
    progress.setWindowTitle("Ažuriranje")
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)
    progress.show()

    def on_progress(pct: int):
        if pct < 0:
            progress.setMaximum(0)
        else:
            if progress.maximum() == 0:
                progress.setMaximum(100)
            progress.setValue(pct)

    def on_done(success: bool, message: str):
        progress.close()
        if success:
            QMessageBox.information(window, "Ažuriranje", "Nova verzija je skinuta. Aplikacija će se ponovno pokrenuti.")
            try:
                apply_update_and_restart(remote_version)
            except FileNotFoundError as e:
                QMessageBox.critical(window, "Ažuriranje nije uspjelo", str(e))
        else:
            # nije kritično: aplikacija nastavlja raditi na trenutnoj verziji, update se ponavlja pri idućem pokretanju
            QMessageBox.warning(window, "Ažuriranje nije uspjelo", f"Radim dalje na trenutnoj verziji.\n\n{message}")

    checker.progress.connect(on_progress)
    checker.download_done.connect(on_done)

    worker = UpdateWorker(checker, mode="download", remote_version=remote_version)
    window._download_worker = worker
    worker.start()


if __name__ == "__main__":
    main()
