% Erzählter Museums-Rundgang in der Suite — Konzept
% For3Dsuite
%

# 1. Ziel

Ein **narrativer, begehbarer Museums-Rundgang**: Besucher folgen einer Erzählung
durch mehrere Räume, verortete **Marker** öffnen **Bilder, Videoclips und
Info-Texte**. Vollständig aus **frei lizenzierten Daten**, self-hostbar, im
vorhandenen Web-Viewer.

# 2. Datenlage (ehrlich geprüft)

**Ein freier CC-Datensatz mit LiDAR *und* 360°-Panos eines Museums existiert nicht.**
Was es gibt:

| Quelle | Was | Lizenz | Eignung |
|---|---|---|---|
| **Museum Barberini, Potsdam** (R. Spekking) | **verbundene 360°-Pano-Serie** mehrerer Säle | **CC-BY-SA 4.0** | **ideal** für Street-View-Rundgang |
| PAIR360 | 360°-Panos **+ LiDAR** | ODbL (frei, Attribution) | nur **outdoor**, kein Museum |
| Stanford 2D-3D-S | 360°-Panos + Punktwolken (indoor) | Forschungslizenz | **nicht** CC-frei, kein Museum |
| Matterport3D / ScanNet | RGB-D + Panos | Forschung/NC | nicht frei |

**Fazit:** Für ein Museum + freie Daten ist der **Street-View-Weg** (verbundene
360°-Panos) der tragfähige. LiDAR-Kopplung und 3DGS-Freilauf bleiben Ausbaustufen,
sobald passende freie Daten vorliegen (oder selbst aufgenommen werden).

# 3. Navigationsmodell — drei Stufen (gleiche Erzähl- und Marker-Logik)

- **Stufe A — Street-View (jetzt, frei):** verbundene 360°-Panos je Raum; im Raum
  freie Blickrichtung, **Sprung** zwischen Räumen über *Portal-Marker* (wie
  Google Street View). Umsetzbar mit den Barberini-Panos, ohne neue Aufnahmen.
- **Stufe B — Pano + Punktwolke:** wenn ein Raum zusätzlich als Punktwolke vorliegt
  (die Suite kann Pano⇄Punktwolke bereits umschalten). Für ein Museum bräuchte es
  einen LiDAR-Scan — aktuell keine freie Quelle.
- **Stufe C — 3DGS-Freilauf (Ausbaustufe):** wirklich freie Bewegung wie beim
  Gaussian Splatting. Kein freies Museums-Splat verfügbar; ließe sich aus einem
  freien Foto-Satz *trainieren* (der 3DGS-Strang der Suite existiert bereits) oder
  vor Ort aufnehmen. Erzählung/Marker bleiben identisch.

**Empfehlung:** Stufe A umsetzen; das Datenmodell so anlegen, dass B/C dieselbe
Tour-Definition weiterverwenden.

# 4. Erzähl-Struktur (Storytelling)

- Eine **Tour = geordnete Sequenz von Stationen** (Knoten). Jede Station ist ein
  Raum-Panorama (später: Splat-Blickpunkt) mit einem **Erzähltext** (Story-Beat).
- **Zwei Modi:**
  - *Geführt:* „Weiter/Zurück" entlang der Erzählung, Kapitel-Fortschritt, optional
    Auto-Kamerafahrt zum nächsten Blickpunkt.
  - *Frei:* selbst erkunden, Portale und Marker frei anklicken.
- **Roter Faden** (Beispiele): eine Zeitreise durch die Sammlung; die Geschichte
  eines Werks/Künstlers; „ein Tag im Museum" aus einer Figur-Perspektive.

# 5. Marker mit Rich Media

Erweiterung der bestehenden Marker-Infobox um **Medientypen**:

| Marker-Typ | Inhalt der Sprechblase |
|---|---|
| **Bild / Galerie** | ein oder mehrere Bilder (CC/Public Domain) + Bildunterschrift |
| **Video** | eingebetteter CC-Clip (lokal gehostet, kein YouTube-Zwang) |
| **Info-Text** | formatierter Erzähl-/Faktentext, Quellenangabe |
| **Portal** | Sprung in einen anderen Raum (Street-View-Übergang) |
| *(optional)* **Audio** | Audioguide-Spur je Station |

Verortung wie die vorhandenen Marker über yaw/pitch im Panorama; Klick öffnet das
Popup mit dem Medium.

# 6. Technische Umsetzung in der Suite

**Wiederverwendet:** Pannellum-Panoramaviewer, Marker/Hotspots, Infobox,
Begehen-Modus, Self-Hosting (Caddy/Garage), statischer Export.

**Neu (klein gehalten):**
- **`tour.json`** (Manifest): geordnete Stationen, je Station `scene`-ID +
  Story-Text + Startblick; **Übergänge** (Portal-Marker → Ziel-Szene + Zielblick);
  Kapitel.
- **Marker-Medien:** Feld `media` je Marker (`type`: image|video|text|portal,
  plus `src`/`caption`/`target`).
- **Tour-Leiste im Viewer:** Titel, Kapitelfortschritt, „Weiter/Zurück",
  Story-Text-Panel; blendet sich im freien Modus aus.
- **Portal-Übergang:** Klick auf Portal-Marker lädt die Ziel-Szene und setzt den
  Startblick (weicher Fade). Datentechnisch ein Marker mit `type:"portal"`.

**Datenmodell:** je Raum eine `scene.json` (wie die bestehenden Pano-Szenen) +
**eine** `tour.json`, die sie zur Erzählung verkettet. So bleibt jede Szene auch
einzeln nutzbar.

# 7. Konkretes Beispiel (Museum Barberini, frei)

- **Räume:** die CC-BY-SA-Panos (Foyer → Saal 1 → Saal 2 → …) als Stationen.
- **Erzählung:** geführter Gang mit Kapiteln (z. B. „Impressionismus in Potsdam").
- **Marker:** an einem Gemälde ein *Bild-Marker* (das Werk als **Public-Domain**-Bild
  von Commons + Werk-Info), an einer Station ein *Info-Text*, wo verfügbar ein
  *CC-Video*; *Portale* führen in den nächsten Saal.
- **Attribution:** Panos „Raimond Spekking / CC BY-SA 4.0"; Werk-Bilder je Quelle.

# 8. Freie Medien-Quellen

- **Panoramen:** Wikimedia Commons (Barberini-Serie u. a.), CC-BY-SA.
- **Werk-Bilder:** Commons — viele Kunstwerke sind **gemeinfrei** (Public Domain),
  keine Attributionspflicht.
- **Videos:** Wikimedia Commons / Vimeo-CC — Verfügbarkeit je Thema prüfen; sonst
  eigener kurzer Clip.
- **Texte:** selbst verfasst oder aus CC-Quellen mit Beleg.

# 9. Ausbaustufen

- **3DGS-Freilauf** (Stufe C), sobald ein freies/aufgenommenes Museums-Splat da ist.
- **Audioguide** (Sprachspur je Station), **Mehrsprachigkeit**.
- **Interaktion:** Quiz/Objekt-Hotspots, „Sammle 5 Werke"-Pfad.
- **Barrierefreiheit:** Textfassung der Tour, Tastatur-Navigation.

# 10. Vorgeschlagene erste Schritte

1. Barberini-Pano-Serie über einen `seed_commons_pano`-artigen Lader holen
   (CC-BY-SA, mit Attribution) → je Raum eine Pano-Szene.
2. `tour.json` + Tour-Leiste im Viewer (geführt/frei) + Portal-Marker.
3. Marker-Popups um Bild/Video/Text erweitern; 2–3 Werk-Marker mit
   Public-Domain-Bildern bestücken.
4. Als Galerie-Szene „Rundgang: Museum Barberini" veröffentlichen.
