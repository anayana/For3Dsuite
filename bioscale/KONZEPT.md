# BioScale – Konzept

Arbeitstitel. Modul der For3Dsuite. Stand: November 2026, Version 0.1 (MVP).

BioScale bringt punktbezogen erhobene Biodiversitätsdaten (Fallen, Fotofallen, Akustik,
Fledermaus-Detektoren, Kartierungen) mit freien Fernerkundungsdaten und optional eigenen Daten
(ALS, TLS, Drohne, eigene Raster) **auf die Fläche**. Zielgruppe sind Ökolog:innen, Förster:innen
und Schutzgebietsverwaltungen **ohne** Spezialwissen in Fernerkundung oder Statistik.

Grundsatz: Vorhandenes verknüpfen (FOSS-Pakete, offene Daten), nicht neu erfinden. Nur freie
Software und offene Daten; keine Google-Dienste.

---

## 1. Problem: Warum die Hochrechnung schwierig ist

### Ökologie
1. **Wirkradius (scale of effect).** Er ist artspezifisch und hängt vom Prozess ab (Nahrung, Brut,
   Ausbreitung). Meist ist er unbekannt und kaum aus Merkmalen der Art vorhersagbar
   (Jackson & Fahrig 2012, Landscape Ecology; 2015, Global Ecology and Biogeography). Er muss
   aus den Daten geschätzt werden. Dabei droht Überanpassung: Man probiert so lange Radien, bis es passt.
2. **Landbedeckung ist nicht Habitat.** Innerhalb einer Klasse entscheidet oft die Intensität:
   Mahd, Düngung, Bestandesalter, Totholz. Kontinuierliche Fernerkundungsvariablen schlagen oft
   diskrete Klassen (arXiv 2509.14862, 2025).
3. **Dimension.** Wald braucht 3D-Struktur (ALS, TLS, Sentinel-1). Offenland braucht den
   Zeitverlauf (Mahd, Ernte, Fruchtfolge).
4. **Zeitverzögerung und Altlasten:** Aussterbeschuld, Landnutzungsgeschichte.
5. **Zielgröße unklar:** Einzelart, Artenzahl, Zusammensetzung oder funktionelle Vielfalt. Die
   Artenzahl hängt vom Maßstab ab. Gestapelte Einzelartmodelle überschätzen sie.

### Daten
6. **Datentypen:** nur Vorkommen, Vorkommen/Fehlen, Zählungen, Fotofallen, Akustik
   (BirdNET, BatDetect2). Dazu kommen Erkennungswahrscheinlichkeit und Aufwand.
7. **Stichproben-Bias**, z. B. Standorte an Wegen.
8. **Zeitlicher Versatz** zwischen Erhebung und Satellitenbild, Wolken.
9. **Wenige Punkte, viele Variablen.** Seltene Arten.

### Statistik
10. **Extrapolation.** Der Gültigkeitsbereich (Area of Applicability, AOA) nach
    Meyer & Pebesma 2021 (Methods in Ecology and Evolution) wird selten ausgewiesen.
11. **Prüfung.** Zufällige Kreuzvalidierung ist zu optimistisch (Roberts et al. 2017, Ecography;
    Ploton et al. 2020, Nature Communications). Besser ist eine räumliche Prüfung, z. B. kNNDM.
12. **Korrelation ist keine Ursache.** Die Übertragbarkeit auf andere Gebiete ist schwach.

### Nutzung
13. **Black-Box-Risiko.** Deshalb braucht es Leitplanken.
14. **Sensible Arten und Formate:** Darwin Core, Camtrap DP. Standorte von Quartieren und Horsten
    dürfen nicht veröffentlicht werden.

---

## 2. Prior Art: Die Bausteine gibt es, die Verknüpfung fehlt

| Baustein | Was es kann | Was fehlt (für unsere Frage) |
|---|---|---|
| biomod2, Hmsc, Wallace, CAST (R); elapid (Python) | Verbreitungsmodelle, gemeinsame Artmodelle, AOA (CAST), Maxent-ähnlich (elapid) | keine Erzeugung von Einflussgrößen aus Fernerkundung, kein Wirkradius als Standard |
| BON in a Box (GEO BON) | Pipeline-Plattform, Verbreitungsmodelle (Maxent, BRT), Stichprobenpriorisierung | global, auf GBIF ausgerichtet; keine fragespezifischen Sentinel-Größen, kein Wirkradius, AOA nicht Pflicht |
| InVEST Habitat Quality | Landbedeckung + Bedrohungen mit Distanzabfall | Expertentabellen statt Punktdaten |
| MALPOLON | Deep-Learning-Verbreitungsmodelle (PyTorch) | kein Wirkradius, kein AOA |
| GeoLifeCLEF / GeoPlant | Europäischer Benchmark | später als Testdatensatz denkbar |

Forschungsstand, an dem sich die Profile orientieren:
- Müller & Brandl 2009: ALS sagt Käfergemeinschaften vorher.
- Bae et al. 2019 (Nature Communications): Sentinel-1 ist für 12 Artengruppen ähnlich gut wie ALS.
  Radar ist besser für die Zusammensetzung, ALS für die Artenzahl. Voraussetzung sind stratifizierte,
  standardisierte Felddaten.
- Zellweger et al. 2016 (Journal of Biogeography): Das Klima erklärt mehr als die Struktur.
- Hilmers et al. 2018: Biodiversität entlang der Sukzession.
- Biodiversitäts-Exploratorien: Baumartendiversität aus Sentinel nur r² = 0,25.
- **Gut** funktionieren strukturgebundene Gruppen: Vögel, Fledermäuse, Totholzkäfer, Pilze.
- **Schwach** bleiben Bodenfauna, die Krautschicht unter dem Buchendach und seltene Arten.
  Spektrale Diversität im Buchen-Kronendach ist schwach und deshalb kein Hauptweg.

Interoperabilität mit BON in a Box wird angestrebt (offene Formate, Pipeline-Idee mit klaren
Schritten und Ein-/Ausgaben); kopiert wird nichts.

---

## 3. Novelty (Leitlinie für das Design)

1. **Durchgängige offene Kette** von den Punktdaten bis zur Karte, einschließlich automatischer,
   fragespezifischer Erzeugung der Einflussgrößen aus freien Fernerkundungsdaten (Profil → Variablengruppen → Layer).
2. **Wirkradius-Schätzung** je Variable innerhalb einer Spanne aus Profilen (Vorwissen), mit
   ehrlicher Prüfung: Die Radiuswahl wird in jeder Prüf-Falte neu gemacht (verschachtelt). Ausgewiesen
   wird eine plausible Spanne (1-SE-Regel). Warnungen gibt es bei flacher Kurve und bei einem Radius am Rand der Spanne.
3. **Leitplanken als Kern, nicht als Option:**
   - Die Karte wird nur im Gültigkeitsbereich gezeigt (AOA-Maske als Standardausgabe).
   - Unsicherheit ist Pflichtausgabe (Cluster-Bootstrap: Streuung, 5- und 95-%-Quantil).
   - Repräsentativitätscheck der Punkte (Abdeckung je Variable, Wege-Bias).
   - Stichprobenvorschlag: wo neue Punkte den Gültigkeitsbereich am stärksten erweitern (GPX/GeoPackage).
   - Ampel im Bericht, Warnungen in einfacher Sprache, „Korrelation ist keine Ursache“ immer sichtbar.
4. **Intensität statt Klasse** als Standardvariable: Mahdereignisse, saisonale Amplitude und
   Störungen aus Sentinel-2-Zeitreihen (Sentinel-1 vorbereitet).
5. **Dieselbe Kette** für Wald (3D: ALS, Sentinel-1) und Offenland (Zeitverlauf).
6. **Zeitreihen:** bei neuen Daten neu rechnen, daraus Veränderungskarten (Phase 2).
7. **Späterer Prüfstand:** Biodiversitäts-Exploratorien (Wald und Grünland, 3 Regionen,
   Intensitätsindizes LUI/ForMI). Die Daten kommen nicht ins Repo, nur eine Schnittstelle (`bioscale.benchmark`).

---

## 4. Architektur

```
projekt.yml ─► occurrence ─► covariates ─► multiscale ─► model ─► validate ─► aoa ─► sampling ─► report
               (DwC, Camtrap DP,  (Sentinel-1/-2, DEM,   (Gauss-Kernel,  (GLM, RF, GBM,   (kNNDM,   (DI nach      (Abdeckung,   (HTML, COG,
                BirdNET,          WorldCover, HRL, DWD,  Radienliste      Maxent; Radius-   Block-CV,  Meyer &       Bias, GPX)    PNG, JSON)
                BatDetect2)       ALS, Drohne, Raster)   aus Profil)      wahl verschachtelt) Metriken) Pebesma)
```

- **Python-Kern** (passt zu `platform/app`: FastAPI, Docker). R nur über eine gekapselte Brücke
  (`bioscale.rbridge`, CSV + Rscript) für Hmsc, spOccupancy und den CAST-Abgleich. Das MVP läuft ohne R.
- **Bibliotheken (FOSS):** numpy, scipy, pandas, geopandas, rasterio, pystac-client, scikit-learn,
  lightgbm, elapid, laspy/lazrs, jinja2, matplotlib, FastAPI.
- **Gemeinsames Raster:** metrisches Koordinatensystem, Standard 10–25 m. Alle Layer werden darauf
  reprojiziert. Ausgaben sind Cloud Optimized GeoTIFFs. Die Herkunft je Layer steht in `herkunft.json`
  (Quelle, Lizenz, Zeitraum, Verarbeitungsschritte, Prüfsumme).

### Module (`src/bioscale/`)

| Modul | Inhalt |
|---|---|
| `project` | YAML-Projektdatei, Prüfung, Assistent (`bioscale wizard`) |
| `occurrence` | Import (Darwin Core CSV/GPKG, Camtrap DP, BirdNET, BatDetect2), Datentyp-Erkennung, Aufwand, Plausibilität, sensible Taxa, Vergröberung, einfaches Occupancy-Modell (p, ψ) |
| `covariates/opendata` | Sentinel-2 L2A (STAC Earth Search oder CDSE; saisonale Mediane NDVI/NDRE/NDMI/NBR, SCL-Maske), Sentinel-1 (STAC, saisonale Statistik), Copernicus DEM GLO-30 (Hangneigung, Exposition, TWI mit D8), ESA WorldCover, Copernicus HRL (Datei), DWD-Raster |
| `covariates/intensity` | Mahdereignisse, saisonale Amplitude, Störung (NDMI-Verlust) |
| `covariates/als` | LAS/LAZ → DTM, normierte Höhe, CHM; Metriken: p95, Mittel, SD, Lückenanteil, Deckung, Foliage Height Diversity, Unterwuchs; auch Drohnen-DSM |
| `multiscale` | NaN-tolerante Kernel-Mittel (Gauß, Kreisscheibe), Klassenanteile, Radienliste |
| `profiles` | YAML je Artengruppe: Variablengruppen, Radienspanne, Modell, Hinweise, Status |
| `model` | schneller Ridge-GLM (IRLS), Random Forest, LightGBM, Maxent (elapid); Radiuswahl, Vorwärtsauswahl, verschachtelte Prüfung, Permutationswichtigkeit, Cluster-Bootstrap |
| `validate` | kNNDM, Block- und Zufallsfolds; AUC, TSS, Boyce, Devianz, Brier, Kalibrierung; R², erklärte Devianz |
| `aoa` | DI und AOA wie CAST (Tukey-Hinges wie R `boxplot.stats`) |
| `sampling` | Abdeckungstabelle, Wege-Bias, gierige AOA-Erweiterung, GPX/GeoPackage |
| `report` | HTML-Bericht in einfacher Sprache mit Karten, Kurven, Tabellen |
| `web` | FastAPI-Assistent (Upload, Profil, Demo, Bericht) |
| `synthetic` | virtuelle Landschaft und virtuelle Art mit bekannter Wahrheit |
| `rbridge`, `benchmark` | R-Brücke; Schnittstelle für Prüfstände |

### Entscheidungen (selbst getroffen, begründet)

- **Wirkradius = 2 σ eines Gauß-Kernels.** Innerhalb davon liegen ca. 86 % des Gewichts. Ein Gauß-Kernel
  ist realistischer als ein harter Puffer. Die Kreisscheibe bleibt wählbar (`kernel: disk`).
- **Radiuswahl univariat je Variable, danach Vorwärtsauswahl.** Der Radius ist eine Eigenschaft der Art
  und der Variable (Jackson & Fahrig). Eine Variable kommt nur ins Modell, wenn sie die räumlich geprüfte
  Vorhersage verbessert. Dadurch werden auch bedingt wichtige Variablen gefunden, z. B. Höhe neben Wald.
- **Gegen Überanpassung:** Die Radiuswahl wird in jeder äußeren Falte wiederholt. Paare mit |r| > 0,7
  werden nicht zusammen verwendet. Höchstens eine Variable je 10 Ereignisse.
- **Standardmodell GLM** (linear + quadratisch, Ridge): robust bei wenigen Punkten, erklärbar.
  RF und GBM laufen zum Vergleich. Gewählt wird nach der räumlichen Prüfung.
- **Zählungen:** Rate je Aufwand mit Aufwand als Gewicht (entspricht einem Offset im Poisson-GLM).
- **Nur Vorkommen:** Maxent (elapid) mit Zielgruppen-Hintergrund. Ersatzweise wird ein Hintergrund
  nach dem Wege-Abstand gewichtet. Sonst gibt es eine Warnung. Die Karte heißt dann „relative Eignung“.
- **Sensible Arten:** eine Startliste (Fledermäuse, Großvögel mit Horsten, Luchs, Wildkatze, Wolf u. a.)
  plus Projektliste. Folgen: Punkte im Bericht vergröbert (Standard 1 km), veröffentlichbare Karten
  blockgemittelt (Standard 250 m), Karten mit voller Auflösung mit Hinweis „nicht veröffentlichen“.
- **Downloads:** nur der benötigte Ausschnitt der Cloud Optimized GeoTIFFs wird gelesen; keine
  ganzen Kacheln.

---

## 5. Nachweis der Kernidee (synthetischer Testfall „virtuelle Art“)

Virtuelle Landschaft (3 × 3 km, 10 m): Waldmosaik, Kronenhöhe, NDVI, Höhengradient West → Ost,
Wegenetz. Die virtuelle Art ist an Wald im Radius **200 m** gebunden und meidet Hochlagen. Dazu kommt
ein unbeobachtetes räumliches Feld. Die Stichprobe ist absichtlich verzerrt: 240 Standorte in Gruppen
an Wegen, nur im Westteil, 3 Begehungen mit Nachweiswahrscheinlichkeit 0,75.

Ergebnis (`bioscale demo`, Seed 42, siehe `tests/test_virtual_species.py` und `tests/test_pipeline.py`):

| Prüfung | Ergebnis |
|---|---|
| Wirkradius der Waldbindung | gewählt 200 m (wahr 200 m), plausible Spanne enthält den wahren Wert |
| Höhenbezug | erkannt (Vorwärtsauswahl) |
| Gültigkeitsbereich | ca. 65 % der Fläche; der Ostteil (Hochlagen, nie beprobt) liegt außerhalb |
| Karte vs. Wahrheit | Korrelation im AOA ca. 0,93, außerhalb ca. 0,70 – der AOA trennt richtig |
| räumliche vs. zufällige Prüfung | Bei naivem Black-Box-Vorgehen (RF, alle Layer × alle Radien) ist die zufällige Prüfung optimistischer (höhere AUC, geringere Devianz) |
| Wege-Bias | erkannt und gewarnt |
| Stichprobenvorschlag | neue Standorte überwiegend im Osten |
| Nachweiswahrscheinlichkeit | p ≈ 0,75 wiedergefunden |

---

## 6. Stand der Downloader (ehrlich)

| Quelle | Mock-Test | echter Abruf in der Cloud-Sitzung |
|---|---|---|
| Sentinel-2 L2A (Earth Search STAC + sentinel-cogs) | ja | **ja** (nach Freigabe des Hosts; dabei Fehler beim BOA-Offset gefunden und behoben) |
| Copernicus DEM GLO-30 (S3) | ja | **ja** |
| ESA WorldCover 2021 (S3) | ja | **ja** |
| DWD CDC, langjährige Mittel (1 km) | ja | **ja** |
| Sentinel-1 (Standard: Planetary Computer `sentinel-1-rtc`) | ja | **nein** – Host gesperrt, Signierung ungetestet |
| Copernicus Data Space (STAC) | Endpunkt und Asset-Namen hinterlegt | **nein** – Zugriff auf die Dateien braucht ein (kostenloses) Konto |
| Copernicus HRL | Datei-Import getestet | Download nur über das CLMS-Portal |
| GBIF (Beispiel `examples/gbif_offene_daten.py`) | – | siehe README |

Sentinel-1 bei Earth Search (`sentinel-1-grd`) liegt in einem Requester-Pays-Bucket und ist damit
nicht kostenlos. Er ist deshalb nicht Standard.

---

## 7. Roadmap

**Phase 1 (MVP, diese Version):** Kette Ende-zu-Ende, virtuelle Art, Downloader, ALS, Profile,
Web-Assistent, Bericht.

**Phase 2:**
- Agrar-Intensität:
  - Mahd aus Sentinel-1/-2 gemeinsam (Radar sieht auch bei Wolken).
  - InVeKoS-/GSAA-Schläge als Einheiten.
  - HRL Small Woody Features.
  - Abgleich mit Referenz-Mahdterminen.
- Occupancy mit Kovariaten (spOccupancy über `rbridge`), Hmsc für Gemeinschaften, integrierte
  Verbreitungsmodelle (z. B. Kartierung + Zufallsfunde).
- Zielgrößen Artenzahl und Zusammensetzung: gemeinsame Modelle statt gestapelter Einzelmodelle.
- Zeitreihen: wiederholte Läufe pro Jahr, Veränderungskarten mit Unsicherheit, Zeitversatz-Prüfung.
- Sentinel-1 über CDSE mit Konto; Copernicus-DEM-Ableitungen bei 10 m aus nationalen DGMs (offen, je Land).
- Lokale Lagegenauigkeit der Punkte berücksichtigen (Kernel × Lageunsicherheit).
- Ausgabe der Vorschläge mit Erreichbarkeit (Wege, Steilheit).
- Integration in `platform/` (Job-Queue, Speicher), QGIS-Plugin als Option.
- Interoperabilität mit BON in a Box: Schritte als Pipeline-Skripte mit deren Ein-/Ausgabeformat.

**Phase 3:**
- Benchmark mit den Biodiversitäts-Exploratorien (Wald und Grünland, LUI/ForMI-Strata) über
  `bioscale.benchmark` – Daten lokal, nicht im Repo.
- Optional GeoPlant (Europa).
- Paper (Abo-Weg, ohne Gebühr), Release über Zenodo mit DOI; im Paper keine GitHub-Links.

---

## 8. Grenzen (bewusst)

- Die Karte zeigt statistische Zusammenhänge, keine Wirkungen. Maßnahmenbewertung braucht Experimente
  oder Vorher-Nachher-Vergleiche.
- Das einfache Occupancy-Modell (ohne Kovariaten) dient nur als Warnsignal, es korrigiert die Karte nicht.
- Die Profile sind **Expertenschätzungen** (Status im Profil). Literatur muss ergänzt werden.
- Die D8-Flussakkumulation ist einfach (keine Senkenfüllung). Für steiles Relief später pysheds/WhiteboxTools.
- Der ALS-Tiefpunktfilter ohne Klassifizierung ist grob. Besser sind klassifizierte Daten (Klasse 2) oder PDAL/SMRF.
