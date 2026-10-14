# Prospekt-Downloader

Lädt die aktuellen Händler-Prospekte als PDF herunter.

| Datei | Zweck |
|---|---|
| `prospekt-downloader.user.js` | Tampermonkey-Userscript (Browser) |
| `lidl_prospekt_auto.py` | Python-Variante für Cronjobs |

## Tampermonkey

1. Tampermonkey öffnen → „Neues Script“ → Inhalt von `prospekt-downloader.user.js` einfügen → speichern.
2. Tampermonkey → Einstellungen (Modus „Fortgeschritten“) → **Downloads**:
   - `.pdf` zu den erlaubten Dateiendungen hinzufügen.
   - Download-Modus **„Browser API“** wählen, damit der Unterordner `prospekte/<händler>/` genutzt wird.
3. Beim ersten Lauf die Cross-Origin-Anfragen (`@connect`) mit „Immer erlauben“ bestätigen.

**Bedienung:** Beim Öffnen von lidl.de wird einmal pro Tag automatisch geprüft. Manuell über das
Tampermonkey-Menü: „Aktuelle Prospekte laden“, „Aktuelle + nächste Woche laden“, „Erneut laden“.

Bereits geladene PDFs merkt sich das Script intern (ein Userscript kann den Download-Ordner nicht lesen).

## Neuen Händler hinzufügen

Im Array `HAENDLER` einen Eintrag mit `id`, `name`, `finden()` und `pdf(p)` ergänzen
(Vorlage steht im Script) und die benötigten Hosts als `@connect` – sowie die Händler-Seite
als `@match` für den Autostart – in den Header eintragen.

## Python: Fehler `CERTIFICATE_VERIFY_FAILED`

Tritt vor allem unter Windows auf, wenn ein Virenscanner-Webschutz oder ein Firmen-Proxy
HTTPS-Verbindungen mit einem eigenen Zertifikat abfängt. Python kennt dieses Zertifikat nicht,
der Browser schon. Abhilfe:

```
pip install truststore
```

Das Script nutzt `truststore` automatisch, falls installiert, und prüft dann gegen den
Zertifikatsspeicher des Betriebssystems – wie der Browser.

## Python: Prospekt verkleinern und durchsuchbar machen (`--klein`)

Der Lidl-Prospekt ist als PDF rund 90 MB groß – und trotzdem kaum durchsuchbar: Lidl bettet
den Text auf fast allen Seiten als Grafik ein (im aktuellen Prospekt haben nur 4 von 73 Seiten
echten Text). Mit `--klein` wird der Prospekt nach dem Download

- verkleinert (jede Seite als JPEG, ca. 15 MB statt 90 MB) und
- per Texterkennung (OCR) mit einer unsichtbaren Textebene versehen – danach lässt sich
  jede Seite durchsuchen und Text markieren/kopieren.

Einmalige Einrichtung:

1. `pip install pymupdf`
2. Tesseract-OCR mit deutschen Sprachdaten installieren:
   - **Windows:** Installer von https://github.com/UB-Mannheim/tesseract/wiki – bei der
     Installation unter „Additional language data“ **German** auswählen. Der Standardordner
     `C:\Program Files\Tesseract-OCR` wird automatisch gefunden.
   - Linux: `sudo apt install tesseract-ocr tesseract-ocr-deu`
   - macOS: `brew install tesseract tesseract-lang`

```
python lidl_prospekt_auto.py --klein            # 120 dpi, ca. 15 MB
python lidl_prospekt_auto.py --klein --dpi=150  # schärfer, ca. 24 MB
```

Die Texterkennung dauert einige Minuten (alle Prozessorkerne werden genutzt). Sie erkennt
Produktnamen und Beschreibungen zuverlässig, groß gesetzte Preise dagegen nicht immer.
