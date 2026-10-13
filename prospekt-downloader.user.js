// ==UserScript==
// @name         Prospekt-Downloader
// @namespace    https://github.com/jake-double-one/prospekt-downloader
// @version      1.0.0
// @description  Lädt die aktuellen Händler-Prospekte (Lidl, später ALDI usw.) als PDF herunter.
// @match        https://www.lidl.de/*
// @grant        GM_xmlhttpRequest
// @grant        GM_download
// @grant        GM_getValue
// @grant        GM_setValue
// @grant        GM_registerMenuCommand
// @grant        GM_notification
// @connect      www.lidl.de
// @connect      endpoints.leaflets.schwarz
// @connect      assets.leaflets.schwarz
// @run-at       document-idle
// @noframes
// ==/UserScript==

(function () {
  "use strict";

  // ---------------------------------------------------------------------------
  // Einstellungen
  // ---------------------------------------------------------------------------
  const EINSTELLUNGEN = {
    // Unterordner im Download-Verzeichnis (funktioniert nur im Tampermonkey-
    // Download-Modus "Browser API", sonst landet alles direkt in Downloads).
    ordner: "prospekte",
    // Beim Öffnen einer passenden Seite automatisch prüfen (max. 1x pro Tag).
    autoStart: true,
  };

  // ---------------------------------------------------------------------------
  // Händler
  //
  // Jeder Händler liefert:
  //   id        – kurzer, eindeutiger Schlüssel
  //   name      – Anzeigename
  //   finden()  – Promise<[{ start: Date, ende: Date, id: string }]>
  //   pdf(p)    – Promise<{ url, groesse? } | null> für einen gefundenen Prospekt
  //
  // Neue Händler: Eintrag hinzufügen und die benötigten Hosts oben als
  // @connect (und ggf. @match) ergänzen.
  // ---------------------------------------------------------------------------
  const HAENDLER = [
    {
      id: "lidl",
      name: "Lidl",
      async finden() {
        const html = await holeText("https://www.lidl.de/c/online-prospekte/s10005610");
        // z.B. aktionsprospekt-12-10-2026-17-10-2026-a1d941
        const muster =
          /\/l\/prospekte\/(aktionsprospekt-(\d{1,2})-(\d{1,2})-(\d{4})-(\d{1,2})-(\d{1,2})-(\d{4})-[0-9a-f]+)/g;
        const gefunden = new Map();
        for (const m of html.matchAll(muster)) {
          const [, id, d1, m1, y1, d2, m2, y2] = m;
          gefunden.set(id, { id, start: datum(y1, m1, d1), ende: datum(y2, m2, d2) });
        }
        return [...gefunden.values()];
      },
      async pdf(p) {
        const data = await holeJson(
          `https://endpoints.leaflets.schwarz/v4/flyer?flyer_identifier=${p.id}&region_id=0&region_code=0`
        );
        const flyer = data.flyer || {};
        const url = flyer.hiResPdfUrl || flyer.pdfUrl;
        return url ? { url, groesse: flyer.fileSize } : null;
      },
    },

    // Vorlage für weitere Händler:
    // {
    //   id: "aldi-sued",
    //   name: "ALDI SÜD",
    //   async finden() { ... return [{ id, start, ende }]; },
    //   async pdf(p) { ... return { url }; },
    // },
  ];

  // ---------------------------------------------------------------------------
  // Hilfsfunktionen
  // ---------------------------------------------------------------------------
  function hole(url, responseType = "text") {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: "GET",
        url,
        responseType,
        timeout: 60000,
        onload: (r) =>
          r.status >= 200 && r.status < 300
            ? resolve(r.response)
            : reject(new Error(`HTTP ${r.status} bei ${url}`)),
        onerror: () => reject(new Error(`Netzwerkfehler bei ${url}`)),
        ontimeout: () => reject(new Error(`Timeout bei ${url}`)),
      });
    });
  }

  const holeText = (url) => hole(url, "text");
  const holeJson = async (url) => {
    const r = await hole(url, "json");
    return typeof r === "string" ? JSON.parse(r) : r;
  };

  const datum = (y, m, d) => new Date(Number(y), Number(m) - 1, Number(d));

  function heute() {
    const h = new Date();
    return new Date(h.getFullYear(), h.getMonth(), h.getDate());
  }

  const fmt = (d) =>
    `${String(d.getDate()).padStart(2, "0")}.${String(d.getMonth() + 1).padStart(2, "0")}.${d.getFullYear()}`;

  /** Aktueller Prospekt (läuft heute, sonst der nächste), optional plus Folgeprospekt. */
  function auswaehlen(prospekte, naechster) {
    const h = heute();
    const sortiert = [...prospekte].sort((a, b) => a.start - b.start);
    const aktuell =
      sortiert.find((p) => p.start <= h && h <= p.ende) ||
      sortiert.find((p) => p.start > h) ||
      sortiert[sortiert.length - 1];
    const auswahl = [aktuell];
    if (naechster) {
      const spaeter = sortiert.find((p) => p.start > aktuell.start);
      if (spaeter) auswahl.push(spaeter);
    }
    return auswahl;
  }

  function download(url, name) {
    return new Promise((resolve, reject) => {
      GM_download({
        url,
        name,
        saveAs: false,
        onload: resolve,
        onerror: (e) => reject(new Error(`Download fehlgeschlagen: ${e && (e.error || e.details) || name}`)),
        ontimeout: () => reject(new Error(`Download-Timeout: ${name}`)),
      });
    });
  }

  // Bereits geladene PDFs merken (Tampermonkey hat keinen Zugriff aufs Dateisystem).
  const geladen = () => new Set(GM_getValue("geladen", []));
  function merken(schluessel) {
    const s = geladen();
    s.add(schluessel);
    GM_setValue("geladen", [...s].slice(-200));
  }

  function melden(text) {
    console.log("[Prospekt-Downloader]", text);
    GM_notification({ title: "Prospekt-Downloader", text, timeout: 6000 });
  }

  // ---------------------------------------------------------------------------
  // Ablauf
  // ---------------------------------------------------------------------------
  async function haendlerLaden(h, { naechster = false, erzwingen = false } = {}) {
    const prospekte = await h.finden();
    if (!prospekte.length) {
      throw new Error(`Keine Prospekte gefunden – vielleicht hat ${h.name} die Seite umgebaut.`);
    }
    let neu = 0;
    for (const p of auswaehlen(prospekte, naechster)) {
      const info = await h.pdf(p);
      const titel = `${h.name} ${fmt(p.start)} – ${fmt(p.ende)}`;
      if (!info) {
        console.warn("[Prospekt-Downloader] Kein PDF für", titel);
        continue;
      }
      const datei = info.url.split("?")[0].split("/").pop();
      const schluessel = `${h.id}/${datei}`;
      if (!erzwingen && geladen().has(schluessel)) {
        console.log("[Prospekt-Downloader] Schon geladen:", titel);
        continue;
      }
      const mb = info.groesse ? ` (${Math.round(info.groesse / 1e6)} MB)` : "";
      melden(`↓ ${titel}${mb}`);
      await download(info.url, `${EINSTELLUNGEN.ordner}/${h.id}/${datei}`);
      merken(schluessel);
      neu++;
    }
    return neu;
  }

  async function alleLaden(optionen = {}) {
    let neu = 0;
    const fehler = [];
    for (const h of HAENDLER) {
      try {
        neu += await haendlerLaden(h, optionen);
      } catch (e) {
        console.error("[Prospekt-Downloader]", h.name, e);
        fehler.push(`${h.name}: ${e.message}`);
      }
    }
    if (fehler.length) melden(`Fehler – ${fehler.join(" | ")}`);
    else if (neu) melden(`✓ ${neu} Prospekt(e) gespeichert`);
    else if (optionen.manuell) melden("Alles aktuell – nichts Neues.");
  }

  GM_registerMenuCommand("Aktuelle Prospekte laden", () => alleLaden({ manuell: true }));
  GM_registerMenuCommand("Aktuelle + nächste Woche laden", () =>
    alleLaden({ manuell: true, naechster: true })
  );
  GM_registerMenuCommand("Erneut laden (auch schon geladene)", () =>
    alleLaden({ manuell: true, erzwingen: true })
  );

  if (EINSTELLUNGEN.autoStart) {
    const tag = fmt(heute());
    if (GM_getValue("letzterLauf") !== tag) {
      GM_setValue("letzterLauf", tag);
      alleLaden();
    }
  }
})();
