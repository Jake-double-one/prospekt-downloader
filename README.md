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

## Python: Prospekt verkleinern (`--klein`)

Der Lidl-Prospekt ist als PDF rund 90 MB groß. Mit `--klein` wird er nach dem Download
verkleinert:

```
pip install pymupdf
python lidl_prospekt_auto.py --klein            # 120 dpi, ca. 16 MB
python lidl_prospekt_auto.py --klein --dpi=150  # schärfer, ca. 24 MB
```

Dabei wird jede Seite als JPEG-Bild gespeichert. Am Bildschirm ist das gut lesbar, der Text
im PDF ist danach aber nicht mehr durchsuchbar oder markierbar. Das Verkleinern dauert etwa
eine Minute.
