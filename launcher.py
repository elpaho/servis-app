r"""
Stabilan launcher za Servis.

Prečac na desktopu UVIJEK pokazuje na launcher.exe (nikad direktno na
servis.exe unutar verzionirane mape). Launcher pročita current.txt i pokrene
aktivnu verziju, pa se sam ugasi. Gotovo se nikad ne mijenja.

Dodatno u odnosu na Cycling Dynamics:
- ako current.txt nedostaje/pokazuje na nepostojeću verziju, pokreće se
  najnovija mapa verzije koja ima servis.exe
- greška se prikazuje u prozoru (bez konzole inače ne bi bila vidljiva) i
  zapisuje u launcher.log
- current.txt se traži uz launcher, a ako ga tamo nema, jednu mapu iznad
  (dopušta layout Servis\launcher\launcher.exe)

Namjerno NE uvozi ništa iz ostatka aplikacije (mora ostati samostalan).
Logika resolve_exe ovdje je ista kao u update_logic.py; test_core.py provjerava
da obje rade jednako.

Build:  python build.py --launcher
"""
import os
import re
import subprocess
import sys

EXE_NAME = "servis.exe"
POINTER_NAME = "current.txt"
_VERSION_RE = re.compile(r"^v\d+(\.\d+)*$")


def _vt(v):
    return tuple(int(p) if p.isdigit() else 0 for p in v.lstrip("vV").split("."))


def find_root(start: str) -> str:
    """Mapa koja sadrži current.txt ili mape verzija: uz launcher, inače jednu iznad."""
    for cand in (start, os.path.dirname(start)):
        if os.path.isfile(os.path.join(cand, POINTER_NAME)):
            return cand
        if os.path.isdir(cand) and any(
            _VERSION_RE.match(n) and os.path.isdir(os.path.join(cand, n)) for n in os.listdir(cand)
        ):
            return cand
    return start


def resolve_exe(root: str):
    pointer = os.path.join(root, POINTER_NAME)
    if os.path.isfile(pointer):
        with open(pointer, "r", encoding="utf-8") as f:
            wanted = f.read().strip()
        if _VERSION_RE.match(wanted):
            p = os.path.join(root, wanted, EXE_NAME)
            if os.path.isfile(p):
                return p
    versions = [n for n in os.listdir(root)
                if _VERSION_RE.match(n) and os.path.isdir(os.path.join(root, n))]
    for name in sorted(versions, key=_vt, reverse=True):
        p = os.path.join(root, name, EXE_NAME)
        if os.path.isfile(p):
            return p
    return None


def _report(root: str, message: str):
    try:
        with open(os.path.join(root, "launcher.log"), "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except OSError:
        pass
    print(message)
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "Servis", 0x10)  # MB_ICONERROR
    except Exception:
        pass


def main() -> int:
    here = os.path.dirname(os.path.abspath(sys.argv[0]))
    root = find_root(here)
    exe = resolve_exe(root)
    if exe is None:
        _report(root, f"Aplikacija nije pronađena u {root}. Provjeri mapu s verzijama (npr. v0.01).")
        return 1
    subprocess.Popen([exe], cwd=os.path.dirname(exe))
    return 0


if __name__ == "__main__":
    sys.exit(main())
