#!/usr/bin/env python3
"""
Lädt automatisch den aktuellen Lidl-Aktionsprospekt (DE) als PDF.

Aufruf:
    python3 lidl_prospekt_auto.py                 # aktueller Prospekt in ./lidl-prospekte
    python3 lidl_prospekt_auto.py ~/Prospekte     # eigener Zielordner
    python3 lidl_prospekt_auto.py --naechster     # zusätzlich den der nächsten Woche
    python3 lidl_prospekt_auto.py --klein         # verkleinert speichern (~90 MB → ~16 MB)
    python3 lidl_prospekt_auto.py --klein --dpi=150   # schärfer, ~24 MB

Schon vorhandene PDFs werden übersprungen – ideal für einen wöchentlichen Cronjob.
Braucht nur Python 3, keine Zusatzpakete – außer für --klein: `pip install pymupdf`.
--klein speichert jede Seite als JPEG-Bild. Das ist am Bildschirm gut lesbar,
aber der Text im PDF ist dann nicht mehr durchsuchbar.

Fehler "CERTIFICATE_VERIFY_FAILED" (oft unter Windows mit Virenscanner-Webschutz
oder Firmen-Proxy): einmalig `pip install truststore` ausführen – dann nutzt das
Script die Zertifikate des Betriebssystems, genau wie der Browser.
"""
import datetime as dt
import json
import pathlib
import re
import ssl
import sys
import urllib.error
import urllib.request

try:  # optional: Zertifikatsspeicher des Betriebssystems verwenden
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

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


def verkleinern(quelle: pathlib.Path, ziel: pathlib.Path, dpi: int):
    """Rendert jede Seite als JPEG und baut daraus ein neues PDF."""
    import pymupdf

    with pymupdf.open(quelle) as src, pymupdf.open() as out:
        for seite in src:
            bild = seite.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=70)
            neu = out.new_page(width=seite.rect.width, height=seite.rect.height)
            neu.insert_image(neu.rect, stream=bild)
        out.save(ziel, garbage=4, deflate=True)


def herunterladen(fid: str, ordner: pathlib.Path, dpi: int | None = None):
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
    if dpi:
        print(f"  … verkleinere auf {dpi} dpi")
        klein = ziel.with_suffix(".klein.part")
        verkleinern(tmp, klein, dpi)
        tmp.unlink()
        tmp = klein
    tmp.rename(ziel)  # erst nach vollständigem Download umbenennen
    print(f"  ✓ Gespeichert: {ziel} ({ziel.stat().st_size / 1e6:.0f} MB)")


def main():
    try:
        laden()
    except urllib.error.URLError as e:
        if not isinstance(e.reason, ssl.SSLCertVerificationError):
            raise
        sys.exit(
            f"SSL-Zertifikat konnte nicht geprüft werden ({e.reason.verify_message}).\n"
            "Meist fängt ein Virenscanner-Webschutz oder ein Firmen-Proxy die Verbindung ab.\n"
            "Lösung: einmalig  pip install truststore  ausführen und das Script erneut starten."
        )


def laden():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    naechster = "--naechster" in sys.argv
    dpi = None
    if "--klein" in sys.argv:
        dpi = next((int(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--dpi=")), 120)
        try:
            import pymupdf  # noqa: F401 – früh prüfen, nicht erst nach dem Download
        except ImportError:
            sys.exit("Für --klein wird PyMuPDF benötigt:  pip install pymupdf")
    ordner = pathlib.Path(args[0] if args else "lidl-prospekte").expanduser()
    ordner.mkdir(parents=True, exist_ok=True)

    for start, ende, fid in auswaehlen(prospekte_finden(), naechster):
        print(f"Aktionsprospekt {start:%d.%m.} – {ende:%d.%m.%Y}")
        herunterladen(fid, ordner, dpi)


if __name__ == "__main__":
    main()
