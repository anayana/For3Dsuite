# BioScale

**Punktdaten zur Biodiversität auf die Fläche bringen – mit Leitplanken.**

Sie haben Fallen, Fotofallen, Vogel- oder Fledermausaufnahmen oder Kartierungen an einzelnen Punkten.
BioScale verknüpft diese Punkte mit freien Satellitendaten (Sentinel-2, Sentinel-1, Höhenmodell,
Landbedeckung) und Ihren eigenen Daten (ALS, Drohne, eigene Karten). Daraus entsteht eine Karte für
das ganze Gebiet. Dazu bekommen Sie immer:

- **Wo die Karte gilt.** Außerhalb des Gültigkeitsbereichs zeigt die Karte nichts. Dort gab es keine vergleichbaren Standorte.
- **Wie unsicher sie ist.** Die Unsicherheitskarte ist Pflicht.
- **Wie gut sie wirklich ist.** Die Prüfung ist räumlich, nicht zufällig, weil eine zufällige Prüfung schönt.
- **Welcher Umkreis (Wirkradius) für die Art zählt.** Er wird aus den Daten geschätzt, innerhalb einer Spanne je Artengruppe.
- **Wo neue Standorte am meisten bringen.** Die Vorschläge kommen als GPS-Datei.
- **Woher jede Zahl kommt.** Quelle, Lizenz und Verarbeitung je Layer.

Alles ist freie Software und läuft auf Ihrem Rechner. Ihre Daten verlassen ihn nicht. Hintergrund und
Methoden: [KONZEPT.md](KONZEPT.md).

---

## 1. Installieren (einmalig)

### Weg A: Standalone-App (ohne Python, ohne Docker) – empfohlen für Nicht-Fachleute

1. Auf GitHub im Repository oben **„Actions“** anklicken, links **„BioScale-App bauen“** wählen.
2. Rechts **„Run workflow“** → **„Run workflow“** klicken. Nach ca. 15 Minuten ist der Lauf grün.
3. Den Lauf anklicken. Unten unter **„Artifacts“** die Datei für Ihr System herunterladen:
   `BioScale-Windows`, `BioScale-macOS` oder `BioScale-Linux`.
4. ZIP entpacken (zweimal: GitHub packt das ZIP noch einmal ein). Im Ordner `BioScale` die Datei
   **`BioScale.exe`** (Windows) bzw. **`BioScale`** (Mac/Linux) doppelklicken.
5. Ein schwarzes Fenster öffnet sich, danach der Browser mit BioScale. Ergebnisse landen im Ordner
   `BioScale` in Ihrem Benutzerordner. Zum Beenden das schwarze Fenster schließen.

Hinweise: Windows fragt beim ersten Start evtl. „Computer geschützt“ → **„Weitere Informationen“ → „Trotzdem
ausführen“** (die App ist nicht signiert). Mac: Rechtsklick auf `BioScale` → **„Öffnen“** → **„Öffnen“**.
Die App ist ca. 550 MB groß, weil sie Python und alle Geodaten-Bibliotheken enthält.
Getestet: Linux-Build in der Cloud (Demo und Web-Oberfläche). Windows/Mac werden erst durch den Workflow gebaut und geprüft.

### Weg B: Python-Paket

Sie brauchen Python ab Version 3.10.

1. Terminal öffnen (Windows: „Eingabeaufforderung“, Mac: „Terminal“).
2. In den Ordner `bioscale` wechseln: `cd pfad/zu/For3Dsuite/bioscale`
3. Eingeben: `pip install -e ".[all]"`

### Weg C: Docker (für Server; in dieser Version noch nicht im Container getestet)


`docker build -t bioscale .` und danach `docker run --rm -p 8765:8765 -v "$PWD/arbeit:/arbeit" bioscale`.

## 2. Ausprobieren mit der Demo (1 Befehl, ca. 10 Sekunden)

```
bioscale demo              # virtuelle Art
bioscale demo --artenzahl  # zusätzlich Artenzahl einer virtuellen Gemeinschaft
```

Das erzeugt eine **virtuelle Art in einem virtuellen Schutzgebiet**. Die Wahrheit ist bekannt
(Wirkradius 200 m). Danach wird alles durchgerechnet. Am Ende steht der Pfad zum Bericht:
`bioscale_demo/ergebnis/bericht.html`. Die Datei per Doppelklick im Browser öffnen.

## 3. Mit eigenen Daten – im Browser (Web-Assistent)

1. Im Terminal eingeben: `bioscale web`
2. Im Browser öffnen: `http://127.0.0.1:8765`
3. Auf **„Demo mit virtueller Art starten“** klicken, um es auszuprobieren, oder das Formular ausfüllen:
   - **Gebiet:** GeoPackage oder GeoJSON mit der Gebietsgrenze (z. B. aus QGIS exportiert).
   - **Punktdaten:** CSV im Darwin-Core-Format (Spalten siehe unten).
   - **Zielart:** wissenschaftlicher Name, genau wie in der CSV.
   - **Artengruppe:** z. B. „Brutvögel im Wald“. Daraus ergeben sich die Variablen und die Radienspanne.
   - **Einflussgrößen:** Haken bei Sentinel-2, Höhenmodell, Landbedeckung (braucht Internet).
     Eigene Raster (GeoTIFF) können Sie dazu hochladen.
4. Auf **„Rechnen“** klicken und warten, bis „Fertig“ erscheint. Dann auf **„Bericht öffnen“** klicken.

## 4. Mit eigenen Daten – Kommandozeile

```
bioscale wizard          # fragt alles ab und schreibt projekt.yml
bioscale run projekt.yml # rechnet und schreibt den Bericht
bioscale profiles        # zeigt alle Artengruppen-Profile
bioscale download projekt.yml   # lädt nur die offenen Daten (z. B. vorab, mit Internet)
```

### Punktdaten (Darwin Core)

| Spalte | Pflicht | Beispiel |
|---|---|---|
| `decimalLatitude`, `decimalLongitude` | ja | 50.1234, 9.5678 (WGS84) |
| `scientificName` | ja | Sitta europaea |
| `occurrenceStatus` | empfohlen | present / absent |
| `locationID` | empfohlen | Standortnummer (für wiederholte Begehungen) |
| `eventID`, `eventDate` | empfohlen | eine Zeile je Begehung und Art |
| `samplingEffort` | empfohlen | „10 min“, „2 h“, „14 Nächte“ |
| `individualCount` | für Zählungen | 3 |

### Zielgrößen

| `question.target` | Was gerechnet wird |
|---|---|
| `occurrence` | Vorkommen einer Art. Bei wiederholten Begehungen (`eventID` je Begehung) prüft BioScale zusätzlich ein **Occupancy-Modell**: Die Karte zeigt dann die Besetzung, korrigiert um übersehene Nachweise. |
| `abundance` | Häufigkeit/Aktivität einer Art (Zählungen, Aufwand als Gewicht) |
| `richness` | **Artenzahl** je Standort aus vollständigen Artenlisten, auf gleich viele Begehungen rarefiziert (`occurrence.rarefy_to`), optional nur eine Gruppe (`occurrence.taxon_filter: {class: Aves}`) |

Gilt eine Liste als vollständige Artenliste (Standard), zählt jede Begehung ohne die Zielart als
„nicht gefunden“. Sonst `complete_lists: false` setzen. Dann rechnet BioScale mit „nur Vorkommen“.

Weitere Formate (Kommandozeile): **Camtrap DP** (Ordner mit `datapackage.json`), **BirdNET**- und
**BatDetect2**-Tabellen (dazu eine Standorttabelle `locationID, latitude, longitude`).

### Beispiel `projekt.yml`

```yaml
name: Mittelspecht im Eichenwald
area: gebiet.gpkg
crs: EPSG:25832
resolution_m: 20
period: {start: 2025-04-01, end: 2025-07-31}
question: {target: occurrence, species: Dendrocoptes medius, profile: voegel_wald}
occurrence: {path: punkte.csv, format: dwc}
covariates:
  open: {sentinel2: true, dem: true, worldcover: true}
  local:
    - {path: kronenhoehe.tif, name: kronenhoehe, group: structure}
  als: {paths: [kachel_1.laz, kachel_2.laz]}
  access: {path: abstand_wege.tif, name: abstand_wege}   # nur für den Bias-Check
sensitive: {taxa: [], coarsen_m: 1000, publish_resolution_m: 250}
output: ergebnis
```

## 5. Was im Ergebnisordner liegt

| Datei | Inhalt |
|---|---|
| `bericht.html` | Bericht in einfacher Sprache (Ampel, Karten, Güte, Wirkradien, Warnungen, Herkunft) |
| `karten/vorhersage_im_aoa.tif` | **die Karte zum Weitergeben** – nur im Gültigkeitsbereich |
| `karten/unsicherheit_sd.tif`, `q05.tif`, `q95.tif` | Unsicherheit |
| `karten/aoa.tif`, `karten/di.tif` | Gültigkeitsbereich (1 = gilt) und Unähnlichkeit |
| `neue_standorte.gpx` / `.gpkg` | Vorschläge fürs Gelände (GPS bzw. QGIS) |
| `einflussgroessen/` | die gewählten Variablen im gewählten Radius |
| `ergebnis.json`, `herkunft.json` | alle Zahlen und die Datenherkunft |
| `veroeffentlichung/` | nur bei sensiblen Arten: vergröberte Karten zum Teilen |

Alle Karten sind GeoTIFFs. In QGIS öffnen Sie sie über *Layer → Layer hinzufügen → Rasterlayer*.

## 6. Sensible Arten

Für Fledermäuse, Großvögel mit Horsten, Luchs, Wildkatze, Wolf u. a. (Liste in `occurrence.py`,
erweiterbar mit `sensitive.taxa`) gilt automatisch:
- Die Punkte im Bericht werden vergröbert (Standard 1 km).
- Die Karten zum Teilen liegen vergröbert in `veroeffentlichung/` (Standard 250 m).
- Die Karten in voller Auflösung tragen den Hinweis „nicht veröffentlichen“.

## 7. Grenzen – bitte lesen

- Die Karte zeigt **Zusammenhänge, keine Ursachen**. Ob eine Maßnahme wirkt, zeigt sie nicht.
- Bei **wenigen Nachweisen** (unter ca. 30–50) ist das Ergebnis unsicher. Der Bericht warnt.
- **Nur-Vorkommen-Daten** (z. B. Zufallsfunde) ergeben eine relative Eignung, keine Wahrscheinlichkeit.
- Die Profile sind **Expertenschätzungen** und müssen geprüft werden. Sie können sie im Projekt anpassen
  (`question.profile_overrides: {radius_m: [20, 400]}`).
- Krautschicht unter dichtem Buchendach, Bodenfauna und seltene Arten sind aus Fernerkundung schwer zu erfassen.

## 8. Für Entwickler:innen

```
pip install -e ".[all,test]"
pytest                          # alle Tests offline (Mocks + synthetische Daten)
BIOSCALE_NETWORK=1 pytest tests/test_network.py   # echte Abrufe (DEM, WorldCover, Sentinel-2, DWD)
python examples/echte_landschaft_virtuelle_art.py   # echte Landschaft + virtuelle Art (Internet)
python examples/gbif_zonienwoud.py               # echte eBird-Daten (GBIF), Zonienwoud bei Bruessel (Internet)
python packaging/build_app.py                    # Standalone-App fuer das eigene Betriebssystem bauen
```

Die R-Brücke (`bioscale.rbridge`) ist optional (Hmsc, spOccupancy, CAST-Abgleich). Das MVP braucht kein R.
Später integrierbar in `platform/` (FastAPI). Ein QGIS-Plugin ist als Option vorgesehen.

Lizenz: GPL-3.0 (wie das Repository, siehe `LICENSE` im Hauptordner).
