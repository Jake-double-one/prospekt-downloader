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
