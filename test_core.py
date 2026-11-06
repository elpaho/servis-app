"""Testovi updater logike, launchera i slaganja release zipa. Pokretanje: python test_core.py"""
import os
import tempfile
import zipfile

import build
import launcher
import update_logic as ul


def mk(root, version, exe="servis.exe"):
    d = os.path.join(root, version)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, exe), "w").close()


# --- verzije
assert ul.is_valid_version("v0.12") and ul.is_valid_version("v1")
for bad in ("", "0.12", "v0.12/..", "..\\x", "v0.1a", "vv1"):
    assert not ul.is_valid_version(bad), bad
assert ul.version_tuple("v0.26") < ul.version_tuple("v0.100") < ul.version_tuple("v1.0")
assert ul.version_tuple("v0.9") < ul.version_tuple("v0.10")          # nije tekstualno uspoređivanje
assert ul.parse_remote_version('VERSION = "v0.26"\n') == "v0.26"
assert ul.parse_remote_version("nema ničega") == ""

# --- pointer i resolve_exe
root = tempfile.mkdtemp()
assert ul.resolve_exe(root, "servis.exe") is None
mk(root, "v0.10"); mk(root, "v0.9"); mk(root, "v0.11")
os.makedirs(os.path.join(root, "v0.12"))                       # mapa bez exe-a (prekinut update)
ul.write_pointer(root, "v0.10")
assert ul.resolve_exe(root, "servis.exe").endswith(os.path.join("v0.10", "servis.exe"))
ul.write_pointer(root, "v0.12")                                  # pointer na pokvarenu verziju -> fallback
assert ul.resolve_exe(root, "servis.exe").endswith(os.path.join("v0.11", "servis.exe"))
ul.write_pointer(root, "../../etc")                              # zlonamjeran/neispravan pointer
assert ul.resolve_exe(root, "servis.exe").endswith(os.path.join("v0.11", "servis.exe"))
assert not os.path.exists(os.path.join(root, "current.txt.tmp"))
assert ul.list_version_dirs(root) == ["v0.12", "v0.11", "v0.10", "v0.9"]

# --- launcher radi isto kao update_logic
assert launcher.resolve_exe(root) == ul.resolve_exe(root, "servis.exe")
os.remove(os.path.join(root, "current.txt"))
assert launcher.resolve_exe(root) == ul.resolve_exe(root, "servis.exe")
assert launcher.find_root(root) == root
sub = os.path.join(root, "launcher"); os.makedirs(sub)           # layout Servis\launcher\launcher.exe
assert launcher.find_root(sub) == root

# --- čišćenje: ostaje 3 najnovije + aktivna + zaštićena; data se ne dira
root2 = tempfile.mkdtemp()
for v in ("v0.1", "v0.2", "v0.3", "v0.4", "v0.5", "v0.6"):
    mk(root2, v)
os.makedirs(os.path.join(root2, "data")); open(os.path.join(root2, "data", "servis.db"), "w").close()
ul.write_pointer(root2, "v0.2")
removed = ul.cleanup_old_versions(root2, keep=3, protect=("v0.1",))
assert sorted(removed) == ["v0.3"], removed                      # v0.4-6 najnovije, v0.2 aktivna, v0.1 zaštićena
assert os.path.isfile(os.path.join(root2, "data", "servis.db"))
assert os.path.isfile(os.path.join(root2, "current.txt"))

# --- zip: exe na vrhu arhive, podmape sačuvane, greška ako exe fali
dist = tempfile.mkdtemp()
open(os.path.join(dist, "servis.exe"), "w").write("x")
os.makedirs(os.path.join(dist, "PyQt6", "Qt6")); open(os.path.join(dist, "PyQt6", "Qt6", "a.dll"), "w").write("y")
zp = os.path.join(tempfile.mkdtemp(), "dist", "servis_latest.zip")
build.make_zip(dist, zp)
names = set(n.replace("\\", "/") for n in zipfile.ZipFile(zp).namelist())
assert names == {"servis.exe", "PyQt6/Qt6/a.dll"}, names
try:
    build.make_zip(tempfile.mkdtemp(), zp); assert False
except FileNotFoundError:
    pass

# --- simulacija cijelog update toka na datotečnoj razini
fam = tempfile.mkdtemp()
mk(fam, "v0.01"); ul.write_pointer(fam, "v0.01")
new = os.path.join(fam, "v0.02")
os.makedirs(new)
with zipfile.ZipFile(zp) as z:
    z.extractall(new)
assert os.path.isfile(os.path.join(new, "servis.exe"))
ul.write_pointer(fam, "v0.02")
assert launcher.resolve_exe(fam).endswith(os.path.join("v0.02", "servis.exe"))

print("SVI TESTOVI PROŠLI (test_core)")
