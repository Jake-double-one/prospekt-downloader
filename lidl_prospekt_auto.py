#!/usr/bin/env python3
"""
Lädt automatisch den aktuellen Lidl-Aktionsprospekt (DE) als PDF.

Aufruf:
    python3 lidl_prospekt_auto.py                 # aktueller Prospekt in ./lidl-prospekte
    python3 lidl_prospekt_auto.py ~/Prospekte     # eigener Zielordner
    python3 lidl_prospekt_auto.py --naechster     # zusätzlich den der nächsten Woche

Schon vorhandene PDFs werden übersprungen – ideal für einen wöchentlichen Cronjob.
Braucht nur Python 3, keine Zusatzpakete.
"""
import datetime as dt
import json
import pathlib
import re
import sys
import urllib.request

UEBERSICHT = "https://www.lidl.de/c/online-prospekte/s10005610"
API = "https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier={id}&region_id=0&region_code=0"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}

# z.B. aktionsprospekt-12-10-2026-17-10-2026-a1d941
MUSTER = re.compile(
    r"/l/prospekte/(aktionsprospekt-(\d{1,2})-(\d{1,2})-(\d{4})-(\d{1,2})-(\d{1,2})-(\d{4})-[0-9a-f]+)"
)


def hole(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def prospekte_finden():
    """Liefert eine nach Startdatum sortierte Liste (start, ende, id)."""
    html = hole(UEBERSICHT).decode("utf-8", "replace")
    gefunden = {}
    for m in MUSTER.finditer(html):
        fid = m.group(1)
        d1, m1, y1, d2, m2, y2 = map(int, m.groups()[1:])
        gefunden[fid] = (dt.date(y1, m1, d1), dt.date(y2, m2, d2), fid)
    if not gefunden:
        sys.exit("Keine Aktionsprospekte auf der Übersichtsseite gefunden – "
                 "vielleicht hat Lidl die Seite umgebaut.")
    return sorted(gefunden.values())


def auswaehlen(prospekte, naechster=False):
    heute = dt.date.today()
    # aktuell: läuft heute, oder (z.B. am Sonntag) der nächste, der startet
    aktuell = next((p for p in prospekte if p[0] <= heute <= p[1]), None) \
        or next((p for p in prospekte if p[0] > heute), prospekte[-1])
    auswahl = [aktuell]
    if naechster:
        spaeter = [p for p in prospekte if p[0] > aktuell[0]]
        if spaeter:
            auswahl.append(spaeter[0])
    return auswahl


def herunterladen(fid: str, ordner: pathlib.Path):
    data = json.loads(hole(API.format(id=fid)))
    flyer = data.get("flyer") or {}
    pdf = flyer.get("hiResPdfUrl") or flyer.get("pdfUrl")
    if not pdf:
        print(f"  ! Kein PDF für {fid}: {data.get('message', '')}")
        return

    ziel = ordner / pdf.rsplit("/", 1)[-1]
    if ziel.exists():
        print(f"  = Schon vorhanden: {ziel.name}")
        return

    groesse = flyer.get("fileSize")
    print(f"  ↓ {ziel.name}" + (f" ({groesse / 1e6:.0f} MB)" if groesse else ""))
    tmp = ziel.with_suffix(".part")
    req = urllib.request.Request(pdf, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    tmp.rename(ziel)  # erst nach vollständigem Download umbenennen
    print(f"  ✓ Gespeichert: {ziel}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    naechster = "--naechster" in sys.argv
    ordner = pathlib.Path(args[0] if args else "lidl-prospekte").expanduser()
    ordner.mkdir(parents=True, exist_ok=True)

    for start, ende, fid in auswaehlen(prospekte_finden(), naechster):
        print(f"Aktionsprospekt {start:%d.%m.} – {ende:%d.%m.%Y}")
        herunterladen(fid, ordner)


if __name__ == "__main__":
    main()
