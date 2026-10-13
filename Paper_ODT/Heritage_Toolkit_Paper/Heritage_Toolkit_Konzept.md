% Memory Twin Toolkit — Paper-B-Konzept
% Offenes Werkzeug zum gemeinschaftlichen Erstellen begehbarer Oral-History-Zwillinge
% Stand: 12.10.2026

# 0. Einordnung

- **Rolle:** Paper B = Werkzeug- und Transferbeitrag. **Nicht** Teil der drei
  Dissertations-Paper (kulturell / sozial / pädagogisch), sondern deren Werkzeug;
  in der Diss. im Methodenteil zitiert.
- **Abgrenzung zu Paper A** (Computers & Geosciences, Panorama-Kette): A = Bildverarbeitung
  (Stitching vs. E57-Reprojektion). B = **Erinnerungsebene + Gaussian Splatting +
  Anleitung** für Laien. B baut auf A auf, wiederholt es nicht.
- **Zieljournale:** Virtual Archaeology Review (Valencia, ES-Kontext) ·
  Digital Applications in Archaeology and Cultural Heritage · JOSS (Softwareteil,
  schnell) · Konferenz-Alternative: CIPA / ISPRS Archives, Digital Heritage.

---

# 1. Kernbeitrag (Reviewer-Test)

Neu sind **nicht** die Einzelwerkzeuge (Photogrammetrie, 3DGS, Panorama-Viewer,
Oral-History-Indexierung existieren). Neu ist:

1. **Erinnerung im Raum verankert:** Zeitzeugen-Clips hängen an Raum, Objekt und
   Zeitschicht (Bauphase/Episode) eines begehbaren Zwillings — statt linear in
   einem Audioarchiv oder stumm in einem 3D-Modell.
2. **Von Laien bedienbar:** Smartphone/Consumer-360° → veröffentlichter
   Erinnerungszwilling, ohne Fachwissen, mit Schritt-für-Schritt-Anleitung.
3. **Ethik eingebaut, nicht angehängt:** Einwilligungsstufen, Widerruf,
   Gemeinschafts-Review vor Veröffentlichung sind Teil des Datenmodells.
4. **Offen und souverän:** FOSS, selbst hostbar oder statisch exportierbar — die
   Erinnerung gehört der Gemeinschaft, nicht einer Plattform.

**Kernaussage für das Abstract:** *Eine Stadtteilinitiative kann mit Smartphone
und offener Software in X Stunden einen begehbaren, ethisch abgesicherten
Erinnerungszwilling eines Wohnhauses erstellen.* (X wird in E1 gemessen.)

---

# 2. Bedarf / Lücke (Statement of need)

- **Oral-History-Archive** sind linear (Audio/Video + Zeitindex, z. B. OHMS) —
  der Raum, über den erzählt wird, fehlt.
- **3D-Dokumentation von Kulturerbe** ist stumm — die Menschen, die den Raum
  bewohnt und verändert haben, fehlen.
- **Gängige Plattformen** (Matterport, Sketchfab u. ä.) sind proprietär,
  cloudgebunden, kostenpflichtig; Rechte und Daten liegen nicht bei der
  Gemeinschaft.
- **Museumswohnungen** (Het Schip, ernst-may-haus, Tautes Heim, MUHBA Bon Pastor)
  zeigen den Bedarf, sind aber an den Ort gebunden und statisch.
- **Lücke:** ein offenes, von Laien bedienbares Werkzeug, das Zeugnis und Raum
  zusammenführt — speziell für kleine, veränderte Wohninnenräume
  (Sozialwohnungsbau, Arbeiterwohnen).

---

# 3. Fragestellungen des Papers (bewusst bescheiden)

- **F1 Machbarkeit:** Können Laien mit Smartphone/Consumer-360° einen nutzbaren
  Erinnerungszwilling eines Innenraums erstellen? (Zeit, Erfolgsrate, SUS)
- **F2 Angemessene Qualität:** Welche Darstellung (Panorama vs. 3DGS) reicht
  wofür? Hauptkriterium ist **Wiedererkennung durch ehemalige Bewohner**, nicht
  der Zentimeter; Geometrie gegen Referenz nur als Nebenprüfung.
- **F3 Verankerung:** Welches Datenmodell trägt Raum, Zeit, Person, Rechte und
  Herkunft eines Zeugnisses — übertragbar auf andere Siedlungen?

---

# 4. Architektur (Schichten)

| Schicht | Inhalt | Werkzeuge (FOSS) | Stand |
|---|---|---|---|
| 1 Aufnahme | Smartphone-Fotos, Consumer-360°, optional iPad-LiDAR | Anleitung + Checkliste | Anleitung fehlt |
| 2 Rekonstruktion | Panorama (Paper-A-Kette) **oder** 3DGS | Hugin; COLMAP; gsplat/Nerfstudio; `build_colmap.py`, `points_to_splat.py`, `clean_splat.py` | Kette da, für Innenräume unerprobt |
| 3 Viewer | begehbarer Raum, Browser + Mobil, optional XR | Pannellum, three.js, Splat-Renderer (`splat.html`) | da |
| 4 Erinnerungsebene | Marker → Clip, Transkript, Übersetzung, Zeitschicht | einheitliches Marker-Schema + `marker-card.js` (Text, Bild, Audio, Video, Links, Zeit, Herkunft); Browser-Studio `create.html` für Laien (offline-fähige HTML-Datei); Transkription Whisper; Index angelehnt an OHMS | **teilweise umgesetzt**: Medien-Marker und Browser-Studio da; Transkription, Zeitschicht-Filter, Mehrsprachigkeit fehlen |
| 5 Rechte & Ethik | Einwilligungsstufen, Pseudonyme, Widerruf, Review | im Datenmodell (Abschn. 5) | fehlt |
| 6 Veröffentlichung | statischer Export oder Self-Hosting | `export_static.py`, GitHub Pages, Caddy/Garage | da |
| 7 Archiv | Langzeitsicherung, zitierbar | Zenodo-DOI; optional Omeka S | fehlt |

**Herkunftsmodell übernehmen** (aus For3Dsuite): jede Aussage im Zwilling trägt
ihre Herkunft — *erinnert* (subjektiv, Zeitzeuge) · *dokumentiert* (Archiv,
Plan, Foto) · *rekonstruiert* (algorithmisch, 3D) · *kuratiert* (Einordnung durch
Museum/Forschung). Das ist methodisch die Brücke zwischen Technik und
Geschichtswissenschaft.

---

# 5. Datenmodell eines Erinnerungs-Markers (Entwurf)

```json
{
  "id": "bp-casa12-cocina-03",
  "anker":    { "typ": "3d", "xyz": [1.42, 0.95, -2.10], "raum": "Küche", "objekt": "Herd" },
  "zeit":     { "von": 1952, "bis": 1968, "bauphase": "Anbau Küche", "episode": "Nachkriegszeit" },
  "zeugnis":  { "person": "P07 (pseudonym)", "rolle": "Bewohnerin 1950–1990",
                "clip": "media/p07_herd.mp4", "dauer_s": 74,
                "transkript": { "ca": "...", "es": "...", "en": "...", "de": "..." } },
  "herkunft": "erinnert",
  "bezug":    ["archiv:MUHBA-Foto-1958-0213"],
  "rechte":   { "einwilligung": "öffentlich", "lizenz": "CC BY-NC-ND 4.0",
                "widerruf_kontakt": "projekt@...", "review": "Gemeinschaft 2027-03" },
  "kuratiert_von": "MUHBA / A. Naya Geiger"
}
```

**Einwilligungsstufen:** `öffentlich` · `nur vor Ort` (Installation, nicht
online) · `nur Forschung` · `gesperrt bis JJJJ`. Der Export filtert automatisch.

---

# 6. Ethik- und Rechte-Modul

- Informierte Einwilligung (Vorlage ca/es/de/en), gestuft wie oben.
- Widerruf jederzeit; Export baut ohne widerrufene Clips neu.
- **Gemeinschafts-Review vor jeder Veröffentlichung** (Bewohner/Angehörige sehen
  den Zwilling zuerst).
- Pseudonymisierung als Standard; Gesichter/Namen in Aufnahmen unkenntlich.
- DSGVO: lokale Verarbeitung, kein Cloud-Zwang.
- Rückgabe: Gemeinschaft erhält Kopie und Rechte am Ergebnis.

---

# 7. Anleitung (How-to) — Gliederung

Zweisprachig/mehrsprachig, je Kapitel eine Checkliste, für Laien geschrieben:

1. **Planen:** Haus, Räume, Zeitzeugen, Rechte klären
2. **Aufnehmen:** Smartphone/360°-Kamera, Licht, Überlappung, Fehlerbilder
3. **Rekonstruieren:** Panorama oder 3DGS — Entscheidungshilfe
4. **Interviewen:** Leitfaden (gemeinsamer Kern + Raum für Anekdoten), Technik
5. **Verankern:** Clips an Raum, Objekt, Zeitschicht hängen
6. **Prüfen:** Gemeinschafts-Review, Einwilligungen abgleichen
7. **Veröffentlichen & sichern:** Export, Installation vor Ort, Zenodo
8. **Vermitteln:** Einsatz in Museum, Schule, Weiterbildung (→ Brücke zu Diss.-Paper 3)

---

# 8. Fallstudie / Demonstration

| Option | Vorteil | Risiko |
|---|---|---|
| **Bon Pastor, Barcelona** (Haupt) | echter Fall, Museum (MUHBA), Bezug zur Diss. | Zugang erst nach Besuch Jan 2027 |
| **Zeugnis des Großvaters** | sofort verfügbar, persönlicher Zugang | nur eine Stimme |
| **Testinnenraum in Bamberg/Deutschland** (Rückfall) | jederzeit erreichbar, Referenzscan über Lehrstuhl möglich | kein Sozialwohnungsbau |
| **PASSTA LunchRoom** (offene Daten) | reproduzierbar für Reviewer | kein Erbe-Kontext |

Empfehlung: Methode an Rückfall-Innenraum + PASSTA entwickeln, Bon Pastor als
Demonstrationsfall nach Januar 2027.

---

# 9. Evaluation

- **E1 Bedienbarkeit (Kern):** Workshop mit 8–12 Laien (Stadtteil, Museumspädagogik,
  Studierende). Aufgabe: vom Foto zum veröffentlichten Erinnerungszwilling.
  Messen: Zeit, Erfolgsrate, Hilfestellungen, SUS. *Vorhandenes Protokoll aus
  Paper A wiederverwenden.*
- **E2 Wiedererkennung:** ehemalige Bewohner sehen Panorama vs. 3DGS —
  „Erkennen Sie Ihr Haus?“ (Likert) + offene Antworten. Das eigentliche
  Qualitätsmaß.
- **E3 Geometrie (Nebenprüfung):** Abweichung gegen iPad-LiDAR oder Laserscan
  (Wolke-zu-Wolke-Abstand, Vollständigkeit) — wenige Zahlen, kein Schwerpunkt.
- **E4 Technik:** Ladezeit/Bildrate auf Mittelklasse-Smartphone, Dateigröße.

---

# 10. Stand: da / fehlt

| Baustein | Stand |
|---|---|
| Panorama-Kette, Viewer, statischer Export, Docker | ✓ da (Paper A) |
| 3DGS-Skripte, Trainings-Notebooks, Demo `renon.splat` | ✓ da, Innenraum unerprobt |
| Rundgang-/Marker-Konzept mit Medien | ✓ Konzept da |
| Nutzbarkeitstest-Protokoll + Formular | ✓ da (aus Paper A) |
| Marker-Datenmodell (Abschn. 5) | ◐ Entwurf hier |
| Marker-Modul im Viewer (Clip, Transkript, Zeitschicht, Einwilligungsfilter) | ✗ fehlt |
| Ethik-/Einwilligungsvorlagen | ✗ fehlt |
| Anleitung (How-to) | ✗ fehlt |
| Innenraum-Fallaufnahme | ✗ fehlt |
| Interviews | ✗ fehlt (Großvater: verfügbar) |
| Evaluation E1–E4 | ✗ fehlt |
| Manuskript | ✗ fehlt |

**Gesamt:** ca. 20 % (nach diesem Konzept), 80 % offen.

---

# 11. Arbeitsplan

| Zeitraum | Schritt |
|---|---|
| Okt–Nov 2026 | Marker-Modul + Einwilligungsfilter im Viewer; Test-Innenraum aufnehmen (Panorama + 3DGS) |
| Nov 2026 | Interview mit Großvater als Pilot; Anleitung Kap. 1–5 im Entwurf |
| **Dez 2026** | **Anmeldung für Besuch im Januar** |
| Jan 2027 | Barcelona: Aufnahme Bon Pastor, Pilot-Interviews, Abstimmung MUHBA |
| **05.02.2027** | **Termin** (klären: Deadline/Treffen?) |
| Feb–Mär 2027 | E1-Workshop, E2 Wiedererkennung, E3/E4 |
| Apr–Mai 2027 | Manuskript, Zenodo-Release, Einreichung |

---

# 12. Grenzen (ehrlich)

- 3DGS braucht dichte Aufnahmen; enge, dunkle Innenräume sind schwierig.
- Wiedererkennung ist subjektiv — bewusst so gewählt, aber nicht verallgemeinerbar
  ohne mehr Fälle.
- Kleine Stichprobe (Workshop n ≈ 10).
- Erinnerung ist selektiv; das Werkzeug macht sie sichtbar, nicht „wahr“ —
  deshalb Herkunftsmodell (*erinnert* vs. *dokumentiert*).
- Langzeitverfügbarkeit von Web-3D bleibt ein offenes Problem.

---

# 13. Arbeitstitel (Auswahl)

- *Memory twins: an open toolkit for co-creating walkable oral-history heritage of working-class homes*
- *Where memory lives: anchoring oral history in low-cost 3D reconstructions of social housing interiors*
- *From smartphone to memory twin: an open, community-operable workflow for intangible heritage in domestic space*
