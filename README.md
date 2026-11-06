# Servis – evidencija servisa bicikala

Mala desktop aplikacija za evidenciju servisnih naloga u biciklističkom servisu.
Radi na jednom Windows 10 laptopu, sama se ažurira preko GitHuba.

> Status dokumenta: **nacrt**. Odjeljci označeni `[OTVORENO]` još nisu odlučeni
> ili provjereni. Kod i testovi (`python test_db.py`, `python test_core.py`) su
> isprobani; Nuitka build i update na stvarnom Windows laptopu još nisu. Na kraju razvoja svaka naredba u ovom dokumentu mora biti
> isprobana i oznake maknute.

---

## 1. Što aplikacija radi

Tijek rada u servisu:

1. Dođe klijent, pretraži se po imenu (radi i bez dijakritika: "coric" nađe "Čorić").
2. Ako ga nema, otvara se novi klijent s osnovnim podacima.
3. Izabere se ili upiše bicikl klijenta.
4. Otvori se servisni nalog za taj bicikl. Datum zaprimanja je današnji,
   po želji se upiše dogovoreni rok.
5. Pri zatvaranju naloga upiše se što je stvarno napravljeno.

Početni ekran je popis otvorenih naloga. Istaknuti su (obojani) nalozi koji:
- su u servisu **N ili više dana** (postavka),
- imaju rok koji ističe za **M ili manje dana** ili je već prošao (postavka).

### Ekrani i tipke

**Glavni prozor** ima tri kartice: *Otvoreni*, *Gotovi* (čekaju preuzimanje), *Preuzeti* (arhiva),
s brojem naloga u naslovu kartice. Pretraga na vrhu filtrira trenutnu karticu po klijentu,
telefonu, biciklu i broju naloga (bez dijakritika; "djuro" nađe "Đuro"). Ako u kartici nema
rezultata, ispiše se da ih potražiš u drugim karticama. Popis se sam osvježava svake minute.

| Tipka | Što radi |
|---|---|
| `Ctrl+N` | novi nalog |
| `Ctrl+F` | skok u pretragu |
| `Esc` | briše pretragu |
| dvoklik ili `Enter` na retku | detalji naloga |

**Novi nalog** (jedan prozor): upiši dio imena ili telefona klijenta; ako je samo jedan rezultat,
odabire se sam. `Enter` u pretrazi odabire prvog i skače na bicikl. Ako klijenta nema,
**+ Novi klijent** (ime se prenese iz pretrage). Bicikl se izabere s popisa klijentovih ili upiše novi.
Zatim opis i po želji rok (kvačica "Dogovoren rok"; datum zaprimanja je današnji).

**Detalji naloga:** otvoren nalog se uređuje (rok, opis), a **Završi nalog** traži unos što je
napravljeno. Otvoren nalog se može i **obrisati** (gumb "Obriši nalog", uz pitanje "jeste li sigurni",
default je "Ne"); to se ne može poništiti. Gotovi i preuzeti nalozi se ne brišu, čuvaju se kao povijest.
Gotov nalog ima **Označi kao preuzet**. Preuzet je samo za pregled.

**Postavke:** koliko dana u servisu je crveno (N), koliko dana do roka je žuto (M),
i automatsko označavanje kao preuzet pri završetku.

Entiteti: **klijent**, **bicikl**, **servisni nalog**, **korisnik**.
Opisi na nalogu su slobodan tekst (što je rekao klijent, što je napravljeno),
bez šifrarnika.

---

## 2. Tehnologije `[ODLUČENO]`

| Dio | Izbor |
|---|---|
| Jezik / UI | Python + PyQt6 |
| Baza | SQLite (jedna datoteka) |
| Kompajliranje | Nuitka `--standalone` (ne onefile) |
| Distribucija i update | GitHub (`elpaho/servis-app`, javan), verzionirani podfolderi + `launcher.exe` |
| Ispis | Termalni printer preko Qt ispisa (model i širina role `[OTVORENO]`) |

Isti pristup kao kod aplikacije Cycling Dynamics (`elpaho/cycling-dynamics-app`).
Na računalu servisa **ne instalira se ništa** (ni Python ni Git).

---

## 3. Datoteke projekta (repozitorij `elpaho/servis-app`)

| Datoteka | Čemu služi |
|---|---|
| `main.py` | ulazna točka; Nuitka direktive; pokreće prozor i provjeru updatea |
| `ui/main_window.py`, `ui/dialogs.py`, `ui/theme.py`, `ui/common.py` | glavni prozor, dijalozi (novi nalog, detalji, postavke), stil, formatiranje datuma |
| `db.py` | baza: shema, migracije, pretraga, nalozi (vidi odjeljak 7) |
| `paths.py` | sve putanje (razvoj vs. kompajlirano) na jednom mjestu |
| `update_logic.py` | čista logika updatera (verzije, `current.txt`, čišćenje); testirana |
| `updater.py` | Qt dio updatera: provjera, skidanje zipa, restart |
| `launcher.py` | stabilni pokretač koji čita `current.txt`; rijetko se mijenja |
| `build.py` | izrada release-a jednom naredbom (odjeljak 6) |
| `version.py` | `VERSION = "v0.XX"`; po njemu laptop zna ima li novog |
| `dist/servis_latest.zip` | gotova kompajlirana aplikacija (jedino što laptop skida osim `version.py`) |
| `test_db.py`, `test_core.py`, `test_ui.py` | testovi baze, updatera/launchera/zipa i ekrana; moraju prolaziti prije svakog release-a |
| `requirements.txt`, `.gitignore` | ovisnosti; što ne ide na GitHub (`data/`, `dist_servis/`, `dist_launcher/`, `cacert.pem`) |

U repozitoriju su **i izvorni kod i gotov izvršni zip**. Laptop servisa s GitHuba čita
samo `version.py` i `dist/servis_latest.zip`; izvorni kod mu ne treba.

---

## 4. Struktura na računalu servisa

```
C:\Servis\                      <- FAMILY_ROOT  [OTVORENO: potvrditi lokaciju]
├── launcher\                   <- sadržaj mape launcher.dist
│   └── launcher.exe  (+ DLL)  <- prečac na desktopu pokazuje ovdje
├── current.txt                <- npr. "v0.12", pokazuje aktivnu verziju
├── v0.11\                      <- stara verzija (čuva se zadnje 3)
├── v0.12\                      <- aktivna verzija
│   └── servis.exe  + DLL/pyd
└── data\                       <- PODACI, izvan verzija, update ih ne dira
    ├── servis.db
    └── backup\
```

Pravila:
- **Podaci nikad ne žive u mapi verzije.** Verzija je zamjenjiva, `data\` nije.
- Launcher traži `current.txt` uz sebe, a ako ga tamo nema, jednu mapu iznad. Zato
  radi i s `launcher.exe` izravno u korijenu i s mapom `launcher\`.
- Ako je `current.txt` pokvaren ili pokazuje na verziju bez exe-a, launcher pokreće
  najnoviju mapu verzije koja ima `servis.exe`. Ako ničega nema, prikaže poruku
  o grešci i zapiše `launcher.log`.

---

## 5. Kako radi automatski update

Samo kad je aplikacija **kompajlirana** (u razvoju, `python main.py`, update se ne radi).

1. Pri pokretanju aplikacija u pozadini dohvati `version.py` s GitHuba
   (`raw.githubusercontent.com`, s timestamp parametrom da zaobiđe CDN cache).
2. Ako je udaljena verzija veća od lokalne, skine `dist/servis_latest.zip`
   i raspakira ga u **novu** mapu `FAMILY_ROOT\vX.YY\`. Stare mape se ne diraju.
3. Provjeri da je u novoj mapi `servis.exe`, atomično prepiše `current.txt`.
4. Pokrene novi exe (`subprocess.Popen`, na zasebnoj niti) i ugasi se (`os._exit(0)`). Prozor
   za to vrijeme prikazuje "Pokrećem novu verziju…": na svježe raspakiranoj mapi Windows Defender
   zna blokirati pokretanje nekoliko sekundi, a na glavnoj niti bi to izgledalo kao "Not responding".
5. Pri svakom pokretanju briše stare mape verzija: ostaje 3 najnovije, aktivna
   i ona koja trenutno radi. `data\` se nikad ne dira.

**Ako update ne uspije** (nema veze, GitHub ne odgovara, neispravan zip): aplikacija
nastavlja raditi na trenutnoj verziji i pokuša ponovno pri idućem pokretanju.

Zašto verzionirane mape: Windows (SysMain / App-Compat) drži zaključan svaki svježe
pokrenuti `.exe`, pa rename/brisanje foldera nije pouzdano. Stara mapa se nikad ne dira.

Zaštite: ime mape verzije mora odgovarati `v<brojevi>.<brojevi>` (ne može se
podmetnuti putanja), a `cacert.pem` nosimo uz exe jer Nuitkin `--include-package-data=certifi` ima poznat bug.

---

## 6. Razvoj i izdavanje

### Razvoj (svakodnevno)
```
python main.py          # pokretanje
python test_db.py       # testovi baze
python test_core.py     # testovi updatera, launchera, zipa
python test_ui.py       # testovi ekrana i radnog tijeka (radi i bez ekrana)
```
`version.py` se **ne mijenja** tijekom razvoja. Commit + push koda može se
raditi bilo kad; to samo sprema izvorni kod, laptop servisa ništa ne primijeti.

### Izdavanje nove verzije
1. Povećaj `VERSION` u `version.py`.
2. `python build.py` (odjeljak ispod).
3. Commit + push **`version.py` i `dist/servis_latest.zip`**. Tek tada laptop vidi novu verziju.

`python build.py` redom: provjeri verziju (staje ako je ista kao objavljena na
GitHubu, `--force` zaobilazi), kopira `cacert.pem` iz certifi, kompajlira Nuitkom u
`dist_servis\main.dist\`, provjeri da `servis.exe` postoji i slaže
`dist/servis_latest.zip` sa sadržajem te mape na vrhu arhive.

| Naredba | Čemu |
|---|---|
| `python build.py` | normalni release |
| `python build.py --debug-console` | exe s konzolom, za traženje grešaka |
| `python build.py --force` | build iako je verzija već objavljena (razvojni build) |
| `python build.py --launcher` | kompajlira samo launcher (rijetko) |

Razvojni build za probu: pokreni `servis.exe` iz `dist_servis\main.dist\` i ne pushaj ništa.

---

## 7. Podaci i baza

Datoteka: `FAMILY_ROOT\data\servis.db` (SQLite). Kod: `db.py`, testovi: `test_db.py`
(pokretanje: `python test_db.py`, mora završiti s "SVI TESTOVI PROŠLI").

| Tablica | Sadržaj |
|---|---|
| `klijent` | naziv, telefon, email, napomena, `naziv_pretraga` (normalizirano za pretragu), aktivan |
| `bicikl` | klijent_id, naziv, napomena, aktivan |
| `nalog` | broj, bicikl_id, datum_zaprimanja, rok, datum_zavrsetka, datum_preuzimanja, status, opis_klijent, opis_radova, otvorio/zatvorio korisnik |
| `korisnik` | ime, pin_hash (PBKDF2, PIN nije prazan tekst), aktivan |
| `postavke` | ključ/vrijednost (vidi dolje) |

Pravila:
- **Klijent se na nalogu ne sprema posebno**, čita se preko bicikla (nema nesklada klijent/bicikl).
- **Klijenti i bicikli se ne brišu**, samo `aktivan = 0`. **Nalog se može trajno obrisati samo dok je otvoren**
  (`db.delete_nalog` odbija gotove i preuzete).
- Datumi su tekst `YYYY-MM-DD`, prikazuju se kao `06.11.2026.`.
- **Broj naloga**: `GODINA-NNNN` (npr. `2026-0142`), redni broj po godini. Zadnje izdani broj pamti se u `postavke` (`zadnji_broj_GODINA`), pa se broj
  obrisanog naloga **nikad ne izdaje ponovno**.
- **Statusi naloga**: `otvoren` -> `gotov` -> `preuzet`. "Gotov" znači da je bicikl
  spreman, "preuzet" da ga je klijent podigao (arhiva).

**Pretraga klijenata** radi bez dijakritika i velikih slova, i po telefonu.
"Coric" nađe "Čorić", a "Djuro" i "Đuro" su isto (i "dj" i "đ" se svode na "d").
Svaka upisana riječ mora se pojaviti u nazivu.

**Isticanje na pregledu otvorenih naloga** (samo status `otvoren`):
- crveno: rok je prošao ILI je nalog u servisu N ili više dana
- žuto: rok ističe za M ili manje dana
- sortiranje: crveno, žuto, ostalo; unutar iste razine najstariji nalog prvi

**Postavke** (tablica `postavke`, zadane vrijednosti u `db.py`):

| Ključ | Zadano | Značenje |
|---|---|---|
| `dana_u_servisu` | 7 | N: nalog u servisu toliko dana ili više postaje crven |
| `dana_do_roka` | 2 | M: rok za toliko dana ili manje postaje žut |
| `auto_preuzet` | 0 | 1 = pri završetku naloga status odmah postaje `preuzet` (preskače `gotov`) |

### Migracije baze
- Verzija sheme je u `PRAGMA user_version`; popis migracija je lista `MIGRATIONS` u `db.py`.
- **Promjena sheme = nova stavka na kraj liste.** Postojeće stavke se nikad ne mijenjaju.
- Pri pokretanju se izvrše sve migracije koje baza još nema, a prije toga se
  postojeća baza kopira u `data\backup\servis_pre_vX_<datum>.db`.
- Ako je baza novije verzije nego što aplikacija zna (netko je pokrenuo staru
  verziju), aplikacija odbija raditi s bazom i traži update. Ne dira podatke.

### Korisnici `[OTVORENO]`
Tablica `korisnik` (ime + PIN hash) i funkcije za PIN postoje u `db.py`, ali **prijave još nema**
u sučelju: nalozi se trenutno otvaraju bez zapisa tko ih je otvorio/zatvorio. Treba odlučiti
treba li uopće (jedna ili dvije osobe u servisu?).

### Backup `[OTVORENO]`
Planirano: dnevna kopija `servis.db` u `data\backup\` (zadnjih X dana).
Odredište izvan računala (USB / oblak) treba dogovoriti s vlasnikom servisa.

---

## 8. Prva instalacija na novo računalo `[OTVORENO: još neisprobano na laptopu servisa]`

1. Kreirati `C:\Servis\` (lokacija `[OTVORENO]`).
2. U nju kopirati: mapu `launcher\` (sadržaj `launcher.dist`), mapu aktivne verzije
   (npr. `v0.12\` iz `dist_servis\main.dist`) i datoteku `current.txt` s tekstom `v0.12`.
3. Napraviti prečac na desktopu prema `launcher\launcher.exe`.
4. Pokrenuti. Zadig/ANT+ driver **nije** potreban za ovu aplikaciju.

Računalu treba internet samo za update; aplikacija bez njega radi, baza je lokalna.

---

## 9. Kad nešto ne radi `[OTVORENO: dopuniti iskustvom]`

- **Aplikacija se ne pokreće nakon updatea:** u `current.txt` upisati prethodnu
  verziju (npr. `v0.11`; zadnje 3 se čuvaju) i pokrenuti ponovno.
- **Launcher javlja "Aplikacija nije pronađena":** provjeriti postoji li mapa
  `vX.YY\servis.exe`; detalji su u `launcher.log` uz launcher.
- **Update se ne dohvaća:** provjeriti internet; `cacert.pem` mora biti uz `servis.exe`.
  Pokrenuti build s `--debug-console` da se vide poruke `[update]`.
- **Antivirus blokira:** dodati iznimku za mapu `C:\Servis`.

---

## 10. Dnevnik odluka

| Datum | Odluka |
|---|---|
| 2026-11-06 | Lokalna aplikacija na jednom laptopu, bez pristupa s drugih uređaja |
| 2026-11-06 | PyQt6 + SQLite + Nuitka standalone, isti updater/launcher kao Cycling Dynamics |
| 2026-11-06 | Podaci izvan version foldera (`data\`), migracije sheme pri startu |
| 2026-11-06 | Laptop je uvijek online (zbog fiskalizacije): ako update ne uspije, aplikacija radi dalje na trenutnoj verziji |
| 2026-11-06 | Dodan status `preuzet`; automatsko postavljanje je postavka `auto_preuzet` (zadano isključeno) |
| 2026-11-06 | Pretraga: "dj" i "đ" izjednačeni; "N dana u servisu" i kašnjenje su obje crveno |
| 2026-11-06 | Repozitorij `elpaho/servis-app` je javan; u njemu su izvorni kod i `dist/servis_latest.zip` |
| 2026-11-06 | Stari folder-swap `updater.exe` se ne koristi; update je ugrađen u aplikaciju |
| 2026-11-06 | Update se ne radi u razvoju (`python main.py`), samo u kompajliranoj aplikaciji |
| 2026-11-06 | Ekrani: tri kartice (otvoreni/gotovi/preuzeti), novi nalog u jednom prozoru, bez automatski označenog retka (krije crveno/žuto) |
| 2026-11-06 | Test updatea na probnoj mapi prošao (v0.01 -> v0.02 automatski). Restart pomaknut na zasebnu nit zbog "Not responding" |
| 2026-11-06 | Naziv prozora: "Servis bicikala Gema" + verzija (konstanta `APP_NAME` u `ui/common.py`) |
| 2026-11-06 | Brisanje: samo otvoreni nalozi, uz potvrdu; broj obrisanog naloga se ne ponavlja |
| 2026-11-06 | Veličina slova u stilu u `pt` umjesto `px` (poruka "QFont::setPointSize: Point size <= 0" na Windowsu) |
