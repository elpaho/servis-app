r"""
Izrada release-a jednom naredbom.

    python build.py                 # kompajlira aplikaciju i slaže dist\servis_latest.zip
    python build.py --debug-console # isto, ali exe ima konzolu (za traženje grešaka)
    python build.py --force         # dopušta build iako je ta verzija već objavljena
    python build.py --launcher      # kompajlira SAMO launcher (rijetko je potrebno)

Što radi (aplikacija):
 1. pročita version.py i usporedi s verzijom objavljenom na GitHubu - ako je ista, staje
    (zaboravljen bump verzije bi značio da laptop servisa ne vidi update)
 2. kopira cacert.pem iz certifi (treba ga Nuitka direktiva u main.py)
 3. Nuitka -> dist_servis\main.dist\
 4. provjeri da servis.exe postoji i složi dist\servis_latest.zip sa sadržajem main.dist\ na vrhu
 5. ispiše što treba commitati i pushati
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile

import update_logic as ul

ROOT = os.path.dirname(os.path.abspath(__file__))
EXE_NAME = "servis.exe"
ZIP_PATH = os.path.join(ROOT, "dist", "servis_latest.zip")
REMOTE_VERSION_URL = "https://raw.githubusercontent.com/elpaho/servis-app/master/version.py"


def read_version() -> str:
    with open(os.path.join(ROOT, "version.py"), encoding="utf-8") as f:
        return ul.parse_remote_version(f.read())


def remote_version():
    """Verzija objavljena na GitHubu, ili None ako se ne može dohvatiti (npr. repo još ne postoji)."""
    try:
        with urllib.request.urlopen(f"{REMOTE_VERSION_URL}?_={int(time.time())}", timeout=8) as r:
            return ul.parse_remote_version(r.read().decode("utf-8"))
    except Exception:
        return None


def make_zip(dist_dir: str, zip_path: str, exe_name: str = EXE_NAME):
    """Zipa SADRŽAJ dist_dir (ne i sam folder) tako da je exe na vrhu arhive."""
    if not os.path.isfile(os.path.join(dist_dir, exe_name)):
        raise FileNotFoundError(f"U {dist_dir} nema {exe_name}")
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for folder, _, files in os.walk(dist_dir):
            for name in files:
                full = os.path.join(folder, name)
                zf.write(full, os.path.relpath(full, dist_dir))


def run_nuitka(args: list):
    cmd = [sys.executable, "-m", "nuitka"] + args
    print("\n>", " ".join(cmd), "\n")
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        sys.exit("Nuitka nije uspjela - build prekinut.")


def build_app(console: bool, force: bool):
    version = read_version()
    if not ul.is_valid_version(version):
        sys.exit(f"version.py ima neispravnu verziju: {version!r} (očekujem npr. v0.12)")
    print(f"Verzija za build: {version}")

    published = remote_version()
    if published is None:
        print("Napomena: ne mogu dohvatiti objavljenu verziju s GitHuba (preskačem provjeru).")
    elif ul.version_tuple(version) <= ul.version_tuple(published) and not force:
        sys.exit(f"Verzija {version} je već objavljena na GitHubu (objavljeno: {published}).\n"
                 "Povećaj VERSION u version.py, ili pokreni s --force za razvojni build.")

    import certifi
    shutil.copyfile(certifi.where(), os.path.join(ROOT, "cacert.pem"))

    out = os.path.join(ROOT, "dist_servis")
    run_nuitka([f"--output-dir={out}",
                f"--windows-console-mode={'force' if console else 'disable'}",
                "main.py"])

    make_zip(os.path.join(out, "main.dist"), ZIP_PATH)
    mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
    print(f"\nGOTOVO: {ZIP_PATH} ({mb:.1f} MB), verzija {version}")
    print("Za objavu: commit + push datoteka version.py i dist/servis_latest.zip")
    print("Za razvojni build (bez objave): ne pushaj ih; probaj exe iz dist_servis\\main.dist\\")


def build_launcher():
    out = os.path.join(ROOT, "dist_launcher")
    run_nuitka(["--standalone", "--windows-console-mode=disable", f"--output-dir={out}", "launcher.py"])
    print(f"\nGOTOVO: {os.path.join(out, 'launcher.dist')}")
    print("Sadržaj te mape ide u Servis\\launcher\\ (prečac pokazuje na launcher.exe unutra).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Build i izrada release zipa za Servis")
    ap.add_argument("--launcher", action="store_true", help="kompajliraj samo launcher")
    ap.add_argument("--debug-console", action="store_true", help="exe s konzolom (debug)")
    ap.add_argument("--force", action="store_true", help="dopusti build iako je verzija već objavljena")
    a = ap.parse_args()
    build_launcher() if a.launcher else build_app(a.debug_console, a.force)
