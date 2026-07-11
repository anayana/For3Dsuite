# animFor — Bausteine 4 & 5: Qualitative Auswertung + Wachstumsmodell

Ergänzung zu `PROJEKT.md`. Deckt die zwei Erweiterungen ab, die aus der reinen
Visualisierung eine vollständige, prognosefähige Bestandesbeschreibung machen.

---

## Baustein 4 — Qualitative Auswertung aus RGB (automatisiert)

### Idee

LiDAR/QSM beschreiben **Struktur** (quantitativ). RGB trägt Information, die in der
Geometrie fehlt (qualitativ): Vitalität, Verfärbung, Nekrosen, Trockenschäden,
Phänologie, Rindenschäden, Pilzfruchtkörper, Rindentextur (artdiagnostisch),
Flechten-/Moosbewuchs, Totholz und Habitatstrukturen. Zusammen ergibt das die
vollständige Bestandesbeschreibung.

### Drei Automatisierungsstufen

| Stufe | Ansatz | Trainingsdaten | Werkzeuge |
|-------|--------|----------------|-----------|
| **1 — klassisches CV** | Farbindizes, Texturmaße (GLCM, LBP) pro Baum/Krone. Vitalitätsproxy = Anteil nicht-grüner Kronenpixel; Rindentextur → Art | keine | R: `terra`, `imager`, `glcm` |
| **2 — trainierte Modelle** | CNN / Vision Transformer für diskrete Klassen (gesund/gestresst/tot, Schaden ja/nein) | annotierte nötig (Flaschenhals) | PyTorch, SegFormer |
| **3 — Vision-Language-Modelle** | zero-shot offene Beschreibung, kein eigenes Training | keine | GPT-4o, Qwen-VL u.a. |

**Empfehlung:** Mit Stufe 1 beginnen (reproduzierbar, publizierbar, keine Blackbox),
zero-shot VLM (Stufe 3) als exploratives drittes Bein.

### Der methodisch entscheidende Punkt

Qualitative Aussagen **nicht** über das Gesamtbild treffen, sondern immer an einen
einzelnen, segmentierten Baum mit ID und Position koppeln:

```
1. Punktwolke segmentieren        → Baum i mit Position + Scanpos-Zuordnung
2. Kronen-/Stamm-Crop je Panorama → Rückprojektion (Mathematik steht in PROJEKT.md)
3. Crop qualitativ auswerten      → Stufe 1 / 2 / 3
4. Ergebnis an Baum i zurückschreiben → georeferenziertes Zustandsattribut
```

Aus „Modell beschreibt Bild" wird ein **baumweiser, georeferenzierter, prüfbarer
Zustandsdatensatz**. Weil jeder Baum aus mehreren Scanpositionen sichtbar ist, über
die Ansichten aggregieren (Mehrheitsvotum, Konfidenzmittelung) — Multi-View steigert
laut aktueller Literatur die Klassifikationsgüte deutlich, besonders bei mittleren
Schadstufen.

### Der Validierungshebel (neu, Paper-würdig)

Qualitativ (RGB) und quantitativ (LiDAR/QSM) am selben Objekt kreuzvalidieren:
VLM meldet „Kronenverlichtung, wenig Feinreisig" → muss sich in geringerer
QSM-Astdichte und Punktdichte der oberen Krone spiegeln. Übereinstimmung = starkes
Signal; Widerspruch = Fehler/Halluzination erkannt. Diese wechselseitige Absicherung
macht die vollständige Bestandesbeschreibung erst belastbar.

### Ehrliche Einordnung

- **Geht heute gut:** Artansprache über Textur, grobe Vitalitätsstufen, auffällige
  Schäden, Habitatstrukturen.
- **Bleibt schwer:** feine Schadstufen (auch Menschen uneinig), Verdeckung im Bestand,
  Domänenlücke (fast alle vortrainierten Modelle kennen Luftbilder, nicht terrestrische
  Kronennahaufnahmen). VLM kann selbstbewusst danebenliegen → geometrische Gegenprobe
  ist Pflicht.

---

## Baustein 5 — Waldwachstumsmodell in der Suite

### Lizenzlage (entscheidet die Modellwahl)

| Modell | Lizenz | Hostbar? | Bemerkung |
|--------|--------|----------|-----------|
| **BWINPro / ForestSimulator** | **GPLv3** (Kern: TreeGrOSS, NW-FVA) | **JA** | Deutscher Praxisstandard, einzelbaumbasiert, 3D-Begehung bereits eingebaut |
| **SILVA** (Pretzsch, TUM) | proprietär | nein (nur mit Vereinbarung) | Wissenschaftl. Gegenpart; Self-Hosting braucht Absprache mit TUM-Lehrstuhl |
| **FORMIND** (UFZ Leipzig) | prüfen | evtl. | Prozess-/kohortenbasiert, passt schlechter zum einzelbaumbasierten LiDAR-Ansatz |

**Entscheidung: BWINPro/ForestSimulator über TreeGrOSS.** Legal hostbar, Praxisstandard,
einzelbaumbasiert, mit eingebauter 3D-Begehung → spricht dieselbe Sprache wie die Suite.

### GPL-Konsequenz und Architektur

- Direktes Einbinden von TreeGrOSS-Code → deine Anwendung wird ableitungsbedingt
  ebenfalls GPLv3 (Quelloffenlegung). Für akademisch/öffentlich meist erwünscht,
  aber bewusste Entscheidung.
- **Sauberer Weg:** TreeGrOSS als eigenständiger Java-Webdienst (z.B. Spring Boot),
  der eine Baumliste per JSON annimmt, simuliert und Zukunftsbestände zurückgibt.
  Hält die GPL-Komponente isoliert, Frontend (JS-Viewer) bleibt separat und modular.
  TreeGrOSS = Java, Verarbeitung = R/Python, Viewer = JS → Service-Trennung ohnehin nötig.

### Eingangsdatensatz — geringer Aufwand, weil deckungsgleich mit der Pipeline

TreeGrOSS braucht im Kern eine **Baumliste** plus Bestandesmetadaten:

| TreeGrOSS-Input | Quelle aus der Pipeline | Aufwand |
|-----------------|-------------------------|---------|
| Position (x,y) | Segmentierung → Stammfuß | gering, fällt an |
| BHD | QSM-Zylinder bei 1,3 m / Stammschnitt | gering |
| Höhe | höchster Punkt des Einzelbaums | trivial |
| **Baumart** | **RGB-Klassifikation = Baustein 4** | mittel |
| Kronenansatz, -breite | aus Punktwolke, optional | mittel |
| Standort/Bonität/Alter | extern (nicht aus LiDAR) | **Hauptlücke** |

Der Modelleingang ist damit kein separates Arbeitspaket, sondern das **Produkt der
Bausteine 1–4**: Geometrie liefert Position/BHD/Höhe, RGB liefert die Art.

### Wo der echte Aufwand liegt (ehrlich)

1. **BHD-Genauigkeit** — Modelle sind auf Feld-BHD kalibriert; LiDAR-BHD hat andere
   Fehlerstruktur (Verdeckung, Rindenrauigkeit, Zylinderfit-Bias). Validierung gegen
   Feldmessung nötig — eigener, publikationswürdiger Schritt, kein Formatierungsproblem.
2. **Bonität/Standort/Alter** kommen nicht aus der Punktwolke — extern beibringen.
   Für bekannte Plots (Renon) dokumentiert; für beliebige Flächen die Hauptlücke.
3. **Dateiformat** ist der kleinste Teil — TreeGrOSS ist offen (Java), erwartetes
   Format direkt im Quellcode ablesbar, Konverter = wenige Tage.

### Was das bewirkt

```
LiDAR + RGB → Bestandesbeschreibung (Position, BHD, Höhe, Art)
            → TreeGrOSS-Baumliste → Simulation über n Jahre
            → Zukunftsbestände zurück in den 3D-Viewer (begehbar)
```

Der Nutzer läuft nicht nur durch den heutigen Wald, sondern durch den in 20 Jahren
prognostizierten — aus einem legal hostbaren, etablierten Modell. Aus „schönen Bildern"
wird ein Vorhersagewerkzeug. Starkes Exposé-Argument Richtung Wachstumskunde.

---

## Umgesetzt in der Suite (For3Dsuite)

- [x] **Stufe-1-CV-Prototyp** — [scripts/qualitative_rgb.py](scripts/qualitative_rgb.py):
  gnomonischer Kronen-Crop je Marker aus dem Equirectangular-Pano, Farbindizes
  (ExG/GLI), GLCM-Textur (numpy), Vitalitätsproxy, Multi-View-Aggregation je
  Marker-ID, Zustandsattribut zurück in `scene.json`. In R geplant, aber in
  Python umgesetzt — konsistent mit der numpy/Pillow-Pipeline und dem Windows-
  R-Segfault. Am Renon-Pano getestet (87 Bäume; 6 bestandesrelativ auffällig).
  Absolute Schadstufen werden bewusst **nicht** behauptet (Domänenlücke): die
  Einstufung ist eine robuste, bestandesrelative Ausreißer-Erkennung.
- [x] **Kreuzvalidierungs-Logik RGB ↔ QSM/LiDAR** —
  [scripts/crossvalidate_rgb_lidar.py](scripts/crossvalidate_rgb_lidar.py):
  RGB-Vitalproxy vs. strukturelle Größe je Baum, robuste z-Scores, Konkordanz/
  Widerspruch je Baum + Spearman-ρ. Idealeingang QSM-Astdichte/Kronendichte;
  Platzhalter aus vorhandenen Attributen.
- [x] **TreeGrOSS-Input-Spezifikation + Konverter** —
  [scripts/treegross_export.py](scripts/treegross_export.py): `scene.json`/CSV →
  Baumlisten-JSON (Artcode-Mapping, Bestandesmetadaten) und Simulationsergebnis →
  `scene.json` (Prognosejahr in die Marker). Pflichtfelder als stabiler JSON-
  Kontrakt festgeschrieben (siehe growth-service).
- [x] **Java-Service-Skizze** — [growth-service/](growth-service/README.md):
  Spring-Boot-Dienst, `POST /simulate` (Baumliste rein, Zukunftsbestand raus),
  GPL-Isolation als eigener Prozess, austauschbare Engine (Stub ohne GPL-JAR /
  echte TreeGrOSS). Kern-Logik + DTOs standalone kompiliert und getestet.
- [x] **Bonität/Standort/Alter für Renon** —
  [data/renon/STANDORT.md](data/renon/STANDORT.md) +
  [data/renon/renon_stand.json](data/renon/renon_stand.json): Standort/Alter/Art
  belegt, Bonität als kenntlich gemachter Platzhalter (noch zu belegen).

### Verbleibend (inhaltlich, nicht Code)

- [ ] Bonität (site index) für Renon belegen statt Platzhalter (Ertragstafel/Feld).
- [ ] LiDAR-BHD gegen Feld-BHD validieren (Kalibrierungsbasis von TreeGrOSS).
- [ ] Echte TreeGrOSS-JAR einbinden (GPL-JAR beziehen, Adapter-Mapping ausfüllen).
- [ ] Stufe 2 (CNN/ViT) / Stufe 3 (VLM zero-shot) als optionale weitere Beine.
