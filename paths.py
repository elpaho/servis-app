r"""
Putanje aplikacije na jednom mjestu.

Produkcija (kompajlirano Nuitkom):
    <FAMILY_ROOT>\
    ├── launcher.exe (ili launcher\launcher.exe), current.txt
    ├── vX.YY\servis.exe ...     <- VERSION_DIR (mapa u kojoj radi ovaj exe)
    └── data\                    <- DATA_DIR (izvan verzija, update ga ne dira)

Razvoj (python main.py): sve je u mapi projekta, podaci u .\data
"""
import os
import sys

IS_COMPILED = "__compiled__" in globals()


def version_dir() -> str:
    if IS_COMPILED:
        return os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.dirname(os.path.abspath(__file__))


def family_root() -> str:
    if IS_COMPILED:
        return os.path.dirname(version_dir())
    return version_dir()


def data_dir() -> str:
    """Može se prebaciti varijablom okoline SERVIS_DATA_DIR (korisno za testove)."""
    path = os.environ.get("SERVIS_DATA_DIR") or os.path.join(family_root(), "data")
    os.makedirs(path, exist_ok=True)
    return path
