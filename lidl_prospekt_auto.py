#!/usr/bin/env python3
"""
Lädt automatisch den aktuellen Lidl-Aktionsprospekt (DE) als PDF.

Aufruf:
    python3 lidl_prospekt_auto.py                 # aktueller Prospekt in ./lidl-prospekte
    python3 lidl_prospekt_auto.py ~/Prospekte     # eigener Zielordner
    python3 lidl_prospekt_auto.py --naechster     # zusätzlich den der nächsten Woche
    python3 lidl_prospekt_auto.py --klein         # verkleinert + durchsuchbar (~90 MB → ~15 MB)
    python3 lidl_prospekt_auto.py --klein --dpi=150   # schärfer, ~24 MB

Schon vorhandene PDFs werden übersprungen – ideal für einen wöchentlichen Cronjob.
Braucht nur Python 3, keine Zusatzpakete – außer für --klein:
`pip install pymupdf` und Tesseract-OCR mit deutschen Sprachdaten.
--klein speichert jede Seite als JPEG-Bild und legt per Texterkennung (OCR) eine
unsichtbare Textebene darüber. Im Original-PDF von Lidl ist der Text fast nur als
Grafik eingebettet – erst so wird der Prospekt überhaupt durchsuchbar.

Fehler "CERTIFICATE_VERIFY_FAILED" (oft unter Windows mit Virenscanner-Webschutz
oder Firmen-Proxy): einmalig `pip install truststore` ausführen – dann nutzt das
Script die Zertifikate des Betriebssystems, genau wie der Browser.
"""
import datetime as dt
import json
import os
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


OCR_DPI = 300  # Auflösung für die Texterkennung (nur intern, nicht im Ergebnis)


def ocr_einrichten():
    """Prüft PyMuPDF und Tesseract (Deutsch); bricht mit Hinweis ab, falls etwas fehlt."""
    try:
        import pymupdf
    except ImportError:
        sys.exit("Für --klein wird PyMuPDF benötigt:  pip install pymupdf")
    standard = pathlib.Path(r"C:\Program Files\Tesseract-OCR\tessdata")
    if not os.getenv("TESSDATA_PREFIX") and standard.is_dir():
        os.environ["TESSDATA_PREFIX"] = str(standard)  # Windows-Installer setzt kein PATH
    try:
        tessdata = pathlib.Path(pymupdf.get_tessdata())
    except RuntimeError:
        tessdata = None
    if not tessdata or not (tessdata / "deu.traineddata").exists():
        sys.exit(
            "Für --klein wird Tesseract-OCR mit deutschen Sprachdaten benötigt.\n"
            "  Windows: https://github.com/UB-Mannheim/tesseract/wiki – bei der\n"
            "           Installation unter 'Additional language data' German auswählen.\n"
            "  Linux:   sudo apt install tesseract-ocr tesseract-ocr-deu\n"
            "  macOS:   brew install tesseract tesseract-lang"
        )
    os.environ["TESSDATA_PREFIX"] = str(tessdata)
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")  # wir parallelisieren selbst pro Seite


def seite_verkleinern(quelle: str, nr: int, dpi: int) -> bytes:
    """Eine Seite: OCR auf scharfem Bild, dann kleines JPEG + unsichtbarer Text."""
    import pymupdf

    with pymupdf.open(quelle) as src:
        seite = src[nr]
        pix = seite.get_pixmap(dpi=OCR_DPI)
        pix.set_dpi(OCR_DPI, OCR_DPI)
        with pymupdf.open("pdf", pix.pdfocr_tobytes(language="deu")) as ocr:
            jpg = seite.get_pixmap(dpi=dpi).tobytes("jpeg", jpg_quality=70)
            p = ocr[0]
            p.replace_image(p.get_images()[0][0], stream=jpg)  # Textebene bleibt
            return ocr.tobytes(garbage=4, deflate=True)


def verkleinern(quelle: pathlib.Path, ziel: pathlib.Path, dpi: int):
    """Baut ein kleines, durchsuchbares PDF; Seiten laufen parallel."""
    import pymupdf
    from concurrent.futures import ProcessPoolExecutor

    with pymupdf.open(quelle) as src:
        anzahl = src.page_count
    with ProcessPoolExecutor() as pool, pymupdf.open() as out:
        jobs = [pool.submit(seite_verkleinern, str(quelle), i, dpi) for i in range(anzahl)]
        for i, job in enumerate(jobs, 1):
            with pymupdf.open("pdf", job.result()) as seite:
                out.insert_pdf(seite)
            print(f"\r  … Seite {i}/{anzahl}", end="", flush=True)
        print()
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
        print(f"  … verkleinere auf {dpi} dpi mit Texterkennung")
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
        ocr_einrichten()  # früh prüfen, nicht erst nach dem Download
    ordner = pathlib.Path(args[0] if args else "lidl-prospekte").expanduser()
    ordner.mkdir(parents=True, exist_ok=True)

    for start, ende, fid in auswaehlen(prospekte_finden(), naechster):
        print(f"Aktionsprospekt {start:%d.%m.} – {ende:%d.%m.%Y}")
        herunterladen(fid, ordner, dpi)


if __name__ == "__main__":
    main()
