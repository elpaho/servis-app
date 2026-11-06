r"""
Čista logika updatera (samo standardna biblioteka, bez Qt-a i mreže) - zato je
lako testirati. Qt dio (skidanje, signali) je u updater.py.

Struktura koju ova logika pretpostavlja:

    FAMILY_ROOT\
    ├── current.txt        <- npr. "v0.12"
    ├── v0.11\servis.exe
    └── v0.12\servis.exe
"""
import os
import re
import shutil

POINTER_NAME = "current.txt"
_VERSION_RE = re.compile(r"^v\d+(\.\d+)*$")


def is_valid_version(v: str) -> bool:
    """'v0.12' je OK. Služi i kao zaštita: ime mape dolazi s interneta."""
    return bool(_VERSION_RE.match(v or ""))


def version_tuple(v: str) -> tuple:
    """'v1.2' -> (1, 2); robustno na neispravne dijelove."""
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def parse_remote_version(text: str) -> str:
    """Iz sadržaja version.py izvuče vrijednost iz linije: VERSION = "vX.XX"."""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("VERSION"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def read_pointer(root: str) -> str:
    path = os.path.join(root, POINTER_NAME)
    if not os.path.isfile(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def write_pointer(root: str, version: str):
    """Atomično: piše u .tmp pa os.replace (isti volumen)."""
    path = os.path.join(root, POINTER_NAME)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(version)
    os.replace(tmp, path)


def list_version_dirs(root: str) -> list:
    """Imena mapa verzija, od najnovije prema najstarijoj."""
    if not os.path.isdir(root):
        return []
    names = [n for n in os.listdir(root)
             if is_valid_version(n) and os.path.isdir(os.path.join(root, n))]
    return sorted(names, key=version_tuple, reverse=True)


def resolve_exe(root: str, exe_name: str):
    """
    Putanja exe-a koji treba pokrenuti, ili None.
    1. verzija iz current.txt, ako njen exe postoji
    2. inače najnovija mapa verzije koja ima exe (zaštita od pokvarenog/praznog pointera)
    """
    wanted = read_pointer(root)
    if is_valid_version(wanted):
        p = os.path.join(root, wanted, exe_name)
        if os.path.isfile(p):
            return p
    for name in list_version_dirs(root):
        p = os.path.join(root, name, exe_name)
        if os.path.isfile(p):
            return p
    return None


def cleanup_old_versions(root: str, keep: int = 3, protect=()) -> list:
    """
    Briše stare mape verzija. Ostaje `keep` najnovijih + aktivna iz current.txt
    + sve u `protect` (npr. mapa u kojoj trenutno radi aplikacija).
    Greške (zaključani fajlovi) se ignoriraju - pokušat će se idući put.
    Vraća imena obrisanih mapa. Mapa data i ostalo što nije mapa verzije se NE DIRA.
    """
    versions = list_version_dirs(root)
    keep_set = set(versions[:keep]) | set(protect)
    current = read_pointer(root)
    if current:
        keep_set.add(current)
    removed = []
    for name in versions:
        if name in keep_set:
            continue
        shutil.rmtree(os.path.join(root, name), ignore_errors=True)
        if not os.path.exists(os.path.join(root, name)):
            removed.append(name)
    return removed
