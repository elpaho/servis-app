from datetime import date

import db

APP_NAME = "Servis bicikala Gema"

STATUS_LABEL = {db.STATUS_OTVOREN: "Otvoren", db.STATUS_GOTOV: "Gotov", db.STATUS_PREUZET: "Preuzet"}


def fmt_date(iso) -> str:
    """'2026-11-06' -> '06.11.2026.'; prazno ostaje prazno."""
    if not iso:
        return ""
    d = date.fromisoformat(iso)
    return f"{d.day:02d}.{d.month:02d}.{d.year}."
