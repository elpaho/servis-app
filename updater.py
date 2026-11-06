r"""
Auto-update preko GitHuba (verzionirane podmape + current.txt + launcher).

Tijek (detaljno u README.md, odjeljak "Kako radi automatski update"):
1. check_for_update: dohvati version.py s GitHuba, usporedi s lokalnom VERSION.
2. download_and_install: skini dist/servis_latest.zip, raspakiraj u NOVU mapu
   FAMILY_ROOT\vX.YY\ (stare mape se ne diraju).
3. apply_update_and_restart: atomično prepiši current.txt, pokreni novi exe, ugasi se.

U razvoju (python main.py) se update NE radi - vidi main.py (paths.IS_COMPILED).
"""
import os
import shutil
import subprocess
import tempfile
import time
import zipfile

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal

import paths
import update_logic as ul
from version import VERSION

GITHUB_USER = "elpaho"
GITHUB_REPO = "servis-app"
GITHUB_BRANCH = "master"

RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
VERSION_URL = f"{RAW_BASE}/version.py"
ZIP_URL = f"{RAW_BASE}/dist/servis_latest.zip"
APP_EXE_NAME = "servis.exe"
KEEP_VERSIONS = 3


def _no_cache_url(url: str) -> str:
    """raw.githubusercontent.com cache-ira par minuta preko CDN-a; timestamp tjera svjež fetch."""
    return f"{url}?_={int(time.time())}"


class UpdateChecker(QObject):
    """Emitira signale iz background threadova (thread-safe UI update)."""
    update_available = pyqtSignal(str)     # udaljena verzija
    no_update = pyqtSignal()
    check_failed = pyqtSignal(str)

    progress = pyqtSignal(int)             # -1 = neodređeno, 0-100 = %
    download_done = pyqtSignal(bool, str)  # uspjeh, udaljena verzija ili poruka greške

    def check_for_update(self):
        try:
            resp = requests.get(_no_cache_url(VERSION_URL), timeout=8)
            resp.raise_for_status()
            remote = ul.parse_remote_version(resp.text)
            if not ul.is_valid_version(remote):
                self.check_failed.emit(f"Neispravna udaljena verzija: {remote!r}")
            elif ul.version_tuple(remote) > ul.version_tuple(VERSION):
                self.update_available.emit(remote)
            else:
                self.no_update.emit()
        except Exception as e:
            self.check_failed.emit(str(e))

    def download_and_install(self, remote_version: str):
        """Skida zip i raspakira ga u FAMILY_ROOT\\<remote_version>\\ - nova, nikad korištena mapa."""
        tmp_path = None
        try:
            if not ul.is_valid_version(remote_version):
                raise ValueError(f"Neispravna verzija: {remote_version!r}")
            target_dir = os.path.join(paths.family_root(), remote_version)
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)  # ostatak prekinutog pokušaja
            os.makedirs(target_dir, exist_ok=True)

            with requests.get(_no_cache_url(ZIP_URL), stream=True, timeout=30) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".zip")
                with os.fdopen(tmp_fd, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if not chunk:
                            continue
                        f.write(chunk)
                        downloaded += len(chunk)
                        self.progress.emit(int(downloaded * 100 / total) if total else -1)

            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(target_dir)

            if not os.path.isfile(os.path.join(target_dir, APP_EXE_NAME)):
                raise FileNotFoundError(f"U zipu nema {APP_EXE_NAME}")
            self.download_done.emit(True, remote_version)
        except Exception as e:
            self.download_done.emit(False, str(e))
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass


class UpdateWorker(QThread):
    """Pokreće provjeru/download u pozadinskom threadu."""
    def __init__(self, checker: UpdateChecker, mode: str, remote_version: str = None):
        super().__init__()
        self.checker = checker
        self.mode = mode  # "check" ili "download"
        self.remote_version = remote_version

    def run(self):
        if self.mode == "check":
            self.checker.check_for_update()
        elif self.mode == "download":
            self.checker.download_and_install(self.remote_version)


def apply_update_and_restart(remote_version: str):
    """
    Zove se NAKON uspješnog download_and_install(). Prepiše current.txt (atomično),
    pokrene novi exe direktno i ugasi ovaj proces (os._exit, ne os.execv - Windows).
    """
    new_exe = os.path.join(paths.family_root(), remote_version, APP_EXE_NAME)
    if not os.path.isfile(new_exe):
        raise FileNotFoundError(f"Novi exe nije pronađen na {new_exe}")
    ul.write_pointer(paths.family_root(), remote_version)
    time.sleep(0.3)  # da se Qt prozori stignu zatvoriti
    subprocess.Popen([new_exe], cwd=os.path.dirname(new_exe))
    os._exit(0)


def cleanup_in_background():
    """Pri startu pospremi stare verzije (ostaje KEEP_VERSIONS najnovijih + aktivna + ova koja radi)."""
    try:
        running = os.path.basename(paths.version_dir())
        ul.cleanup_old_versions(paths.family_root(), keep=KEEP_VERSIONS, protect=(running,))
    except Exception:
        pass
