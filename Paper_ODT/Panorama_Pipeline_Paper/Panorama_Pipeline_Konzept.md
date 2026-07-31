% Automatisierte, quelloffene Kette für begehbare 360°/3D-Web-Visualisierungen aus Mehrbild-Aufnahmen — Paper-Konzept
% For3Dsuite
%

# Kurzfassung des Beitrags

Eine **containerisierte, quelloffene (FOSS) Verarbeitungskette mit grafischer
Oberfläche**, die Mehrbild-Aufnahmen automatisiert in **begehbare, web-basierte
360°/3D-Szenen** überführt und diese optional mit aus Punktwolken abgeleiteten
Fachdaten (Inventur) verknüpft. Der wissenschaftliche Beitrag liegt nicht in den
Einzelwerkzeugen (die sind bekannt), sondern in der **Integration**:

1. **Zwei Eingangsklassen, eine Pipeline.** Das Werkzeug erkennt automatisch, ob
   **Kameraposen vorliegen**:
   - *nein* (Consumer/DSLR-Fisheye — Sony A7R + Samyang 8 mm + Nodalpunktadapter,
     Ricoh Theta, Insta360) → **Stitching** (Hugin, Kontrollpunkte);
   - *ja* (**RGB-Bilder terrestrischer Laserscanner**, im E57 mit Pose gespeichert)
     → **direkte Reprojektion** ins Equirektangulare, ohne Stitching.
2. **Wiederverwertung der Scanner-RGB-Bilder** — meist nur ein Nebenprodukt zum
   Einfärben der Punktwolke — als eigenständige, begehbare Panoramen **und** als
   Träger der abgeleiteten Bestandesdaten. Das ist der unterexplorierte Teil.
3. **Datensouveränität**: vollständig **self-hostbar** (Caddy + Garage), **in
   Docker**, mit GUI — kein Cloud-Zwang, reproduzierbar, DSGVO-freundlich.
4. **Geräte- und kostenagnostisch**: vom ~20-€-360°-Consumer-Setup bis zum
   50-k€-TLS-Scanner in dieselbe Web-Szene.

**Zieljournal (Vorschlag):** primär *SoftwareX* (Elsevier; Original Software
Publication, WoS/Scopus, verlangt öffentliches Repo + Reproduzierbarkeit).
Alternativ *Environmental Modelling & Software* (höherer IF, wenn die Wald-/
Umwelt-Anwendung stärker gewichtet wird) oder *ISPRS Int. J. of Geo-Information*
(photogrammetrisch-räumliche Rahmung, Open Access). Manuskriptsprache: Englisch.

---

# Arbeitstitel (Auswahl)

- *An open, containerized pipeline turning multi-image captures — from consumer
  360° cameras to terrestrial laser scanners — into web-navigable 3D scenes.*
- *From six fisheye frames to a walkable web scene: a FOSS, self-hostable
  panorama-to-3D toolchain unifying stitching and scanner-image reprojection.*

---

# Abstract (Entwurf, DE — final EN)

Begehbare 360°-Panoramen und Punktwolken sind wertvoll für Dokumentation,
Monitoring und Vermittlung, ihre Erzeugung ist jedoch meist an proprietäre,
cloud-gebundene Werkzeugketten geknüpft. Wir stellen eine vollständig quelloffene,
containerisierte Verarbeitungskette mit grafischer Oberfläche vor, die
Mehrbild-Aufnahmen automatisiert in begehbare, web-basierte 3D-Szenen überführt.
Die Kette vereint zwei bislang getrennt behandelte Eingangsklassen: (i) Aufnahmen
ohne bekannte Pose (Consumer- und DSLR-Fisheye), die per Stitching (Hugin)
zusammengesetzt werden, und (ii) die RGB-Bilder terrestrischer Laserscanner, deren
Posen im E57-Format hinterlegt sind und die daher direkt reprojiziert werden — ein
selten genutztes Nebenprodukt. Die Ausgabe wird mit einem quelloffenen Web-Viewer
(Pannellum, three.js) dargestellt, self-hostbar über Caddy und Garage, komplett in
Docker gekapselt. In einer Evaluation quantifizieren wir Stitching-Genauigkeit
gegen CC0-Panoramen als Referenz, vergleichen posen-basierte Reprojektion mit
posen-geschätztem Stitching auf identischer Szene und erfassen Aufwand, Laufzeit
und Nutzbarkeit über das Geräte-Spektrum. Über 11 CC0-Referenzpanoramen ist der
posen-basierte Zweig dem Stitching in allen Maßen überlegen (26,9 gegen 23,0 dB
PSNR, 0,886 gegen 0,837 SSIM, 0,10 gegen 0,14 px Nahtversatz), rekonstruiert alle
11 Szenen gegenüber 6 und ist dabei siebenmal schneller.

---

# 1. Einleitung und Motivation

- Bedarf: begehbare visuelle Dokumentation von Standorten (Wald-Monitoring,
  Vermessung, Kulturerbe, Lehre) — reproduzierbar, ohne Vendor-Lock-in.
- Problem: gängige Wege sind proprietär (Kamera-Apps, Cloud-Hosting) oder
  fragmentiert (Stitching-Tool ↔ Viewer ↔ Server manuell verbinden).
- Lücke: (a) keine offene, containerisierte End-to-End-Kette mit GUI; (b) die
  posen-bekannten Scanner-RGB-Bilder werden kaum als eigenständige Panoramen
  weiterverwertet.

# 2. Verwandte Arbeiten und Abgrenzung (Novelty)

- Stitching/Photogrammetrie: Hugin/Panotools, OpenPano, kommerzielle Suiten.
- Web-Panorama-Viewer: Pannellum, Marzipano, three.js.
- TLS-Sphärenbilder: Scanner-Software kann Panoramen exportieren; Literatur zu
  spherical imaging existiert.
- **Abgrenzung (ehrlich):** Neu ist nicht ein Einzelbaustein, sondern die
  **offene, containerisierte, GUI-gestützte, herstellerunabhängige Vereinigung
  beider Eingangsklassen** samt Verknüpfung mit aus der Punktwolke abgeleiteten
  Fachdaten. „Wird nie gemacht" wäre zu stark; der Beitrag liegt in Integration,
  Offenheit und Reproduzierbarkeit.

# 3. Systemarchitektur

## 3.1 Zwei Eingangsklassen, eine Pipeline

| | Consumer/DSLR-Fisheye | Scanner-RGB (E57) |
|---|---|---|
| Kameraposen | unbekannt (zu schätzen) | **bekannt** (im E57) |
| Geometrie-Schritt | **Stitching** (Kontrollpunkte, Nodal-Kalibrierung) | **Reprojektion** ins Equirect |
| Aufwand / Fehlerquelle | höher (Parallaxe, Nahtversatz) | niedrig, automatisch, nahtlos |
| Hardware-Spanne | 20 €–5000 € | 20 000 €–150 000 € |

Automatische Fallunterscheidung: Posen vorhanden → reprojizieren; sonst → stitchen.
Umgesetzt in `platform/app/pipeline.py` (`detect_input_class`, Job-Typ `auto`,
Voreinstellung im Studio): `.e57` im Upload → Reprojektion; genau ein Bild im
Seitenverhältnis 2:1 → fertiges Equirect; mehrere Bilder → Stitching. Bei einem
einzelnen Nicht-2:1-Bild wird bewusst **nicht geraten**, sondern ein Fehler
gemeldet. Im Container verifiziert: derselbe Upload-Endpunkt ohne Typangabe
erkennt `equirect` (ein 2:1-Bild) bzw. `fisheye` (sechs Aufnahmen) korrekt und
führt die jeweilige Kette bis zur veröffentlichten Szene durch.

## 3.2 FOSS-Bausteine
- **Hugin/Panotools** — Stitching (Kontrollpunkte, Projektion, Blending).
- **GIMP (Batch/Script-Fu)** — Vorverarbeitung (Belichtung, Zuschnitt, Nadir/Zenit).
- **Pannellum / three.js** — web-basierter Panorama- und Punktwolken-Viewer.
- (Optional) **Reprojektion** posen-bekannter Bilder → Equirect (eigenes Skript).

## 3.3 Self-Hosting und Container
- **Caddy** — Reverse Proxy, automatisches HTTPS.
- **Garage** — S3-kompatibler, self-hosted Objektspeicher für Medien.
- **Docker (Compose)** — reproduzierbare Gesamtumgebung; ein Befehl → lauffähiger
  Stack (Verarbeitung, Speicher, Server, GUI).
- **GUI** — Upload, Verarbeitung, Szenen-Kuratierung, ohne Kommandozeile.

## 3.4 Verknüpfung mit Fachdaten (Alleinstellung bei Scanner-Daten)
- Aus derselben E57-Punktwolke abgeleitete Inventur (Stammdetektion, BHD, Höhe,
  Kronenmetriken, QSM, Wachstumsprognose) wird als **georeferenzierte Marker** in
  die begehbare Szene gelegt — Panorama und Datenträger in einem.

# 4. Verarbeitungsschritte (Workflow)

1. Import (6+ Einzelbilder je Standpunkt; E57 mit Bildern+Posen erkannt).
2. Vorverarbeitung (GIMP-Batch).
3. Geometrie: Reprojektion (posen-bekannt) **oder** Stitching (Hugin).
4. Export Equirektangular (+ Kacheln/Multi-Auflösung).
5. Szenen-Manifest + Viewer (Pannellum/three.js).
6. Optional: Punktwolke + Inventurmarker koppeln.
7. Veröffentlichung self-hosted (Caddy/Garage) oder statisch.

# 5. Evaluation

Umgesetzt in `scripts/`: `pano_to_views.py` (Referenzpanorama → synthetische
Aufnahmen mit exakt bekannter Pose), `stitch_hugin.py` (Hugin ohne GUI),
`reproject_pano.py` (posen-basiert), `eval_pano.py` (PSNR/SSIM/Abdeckung/Yaw),
orchestriert von `eval_pipeline.py`. Rohdaten: `data/_eval/ergebnisse.csv`.

## 5.1 / 5.2 Stitching vs. Reprojektion gegen CC0-Referenz — Ergebnisse

Aus jedem der **11 CC0-Panoramen** (Poly Haven, 8192×4096) werden synthetische
Aufnahmen gerendert und daraus wieder ein Panorama (2048×1024) gebaut — einmal
per Stitching aus 6 Fisheye-Aufnahmen (180°, Pose *nicht* verraten), einmal per
Reprojektion aus 6 Pinhole-Aufnahmen + Zenit/Nadir (90°, Pose genutzt). Beide
werden gegen dasselbe Original gemessen.

| Zweig | erfolgreich | PSNR (dB) | SSIM | Nahtversatz (px) | Laufzeit |
|---|--:|--:|--:|--:|--:|
| Stitching (Pose geschätzt) | **6 / 11** | 22,98 ± 2,74 | 0,837 ± 0,060 | 0,14 (p95 0,53) | 14,6 s |
| Reprojektion (Pose bekannt) | **11 / 11** | **26,87 ± 1,96** | **0,886 ± 0,039** | **0,10 (p95 0,23)** | 2,1 s |

Der posen-basierte Zweig ist in **allen** Maßen besser: +3,9 dB, +0,05 SSIM, ein
Drittel weniger lokale Verschiebung (p95 weniger als die Hälfte) — und er
rekonstruiert alle 11 Szenen, während Stitching an 5 scheitert: dreimal bricht
`enblend` ab (»excessive image overlap«, »degenerate image/mask geometry«,
»failed to detect any seam«), zweimal entsteht ein geometrisch falsches Panorama.
Letzteres ist kein Messartefakt: auch unter erschöpfender Suche über Drehung,
Neigung und Spiegelung kommen diese beiden nicht über 11,7 dB.

### Nahtversatz als automatisches Qualitätsmerkmal

Der Nahtversatz wird blockweise per Phasenkorrelation gegen die Referenz gemessen
(64-px-Blöcke, 50 % Überlappung; strukturarme Blöcke verworfen). Er trennt
gelungene von misslungenen Rekonstruktionen **schärfer als PSNR oder SSIM**:

| | brauchbare Stitches | misslungene Stitches | Reprojektion |
|---|--:|--:|--:|
| Nahtversatz Median | 0,11–0,19 px | **5,95 / 6,14 px** | 0,07–0,13 px |

Das ist ein Faktor ~40 zwischen gelungen und misslungen, ohne Kenntnis der
Wahrheit einer einzelnen Szene interpretierbar. Für den in Abschnitt 9 genannten
**automatischen Qualitätsflag in der GUI** ist damit ein belastbarer Schwellwert
verfügbar (hier: > 1 px Median). PSNR allein taugt dafür schlechter, weil er auch
auf Belichtung und Schärfe reagiert.

Einzelwerte (PSNR dB · Nahtversatz px, Stitching / Reprojektion): forest-slope
22,4·0,17 / 26,3·0,10 · furstenstein —/27,0·0,11 · hochsal —/24,5·0,11 ·
monks 24,9·0,11 / 27,9·0,07 · mossy 19,8·0,14 / 28,2·0,07 · nature-reserve
20,2·0,13 / 24,9·0,09 · niederwihl ✗ 11,7·6,14 / 23,3·0,13 · quadrangle
—/28,3·0,12 · sunset 23,9·0,19 / 27,8·0,10 · symmetrical-garden ✗ 8,6·5,95 /
27,3·0,10 · woods 26,8·0,12 / 30,0·0,07.

### Grenzen dieser Zahlen (wichtig)

- **Kein Parallaxenfehler.** Alle synthetischen Aufnahmen teilen denselben
  Nodalpunkt. Das ist der *günstigste denkbare Fall* fürs Stitching; reale
  Aufnahmen mit Nodalpunktversatz können nur schlechter werden. Die
  Stitching-Zahlen sind damit **obere Schranken**.
- **Kein Sensorrauschen, keine Belichtungsunterschiede, keine Verzeichnung** —
  die synthetischen Bilder sind ideal. Gemessen wird die Geometrie der Kette,
  nicht die Bildqualität einer Kamera.
- Die absolute PSNR-Höhe ist durch die Auflösungskette gedeckelt (8k-Referenz →
  1400–1600 px Einzelbilder → 2048 px Ausgabe) und daher **nur im Vergleich der
  beiden Zweige aussagekräftig**, nicht als Absolutwert.
- Die Zahlen der Reprojektion gelten erst seit der Umstellung auf **bilineare
  Abtastung**. Mit der zuvor verwendeten Nächster-Nachbar-Abtastung lag derselbe
  Zweig bei 25,4 dB / SSIM 0,871 statt 28,2 / 0,935 (Beispiel ph-mossy-forest)
  und damit im SSIM *hinter* dem Stitching — ein reines Implementierungsartefakt,
  das beinahe als Verfahrenseigenschaft berichtet worden wäre.
- Die 5 Fehlschläge sind Hugin-Voreinstellungen ohne szenenspezifische
  Nachjustierung — ein erfahrener Anwender würde einige davon von Hand retten.
  Genau das ist aber der Punkt: die Kette soll **automatisch** laufen.

## 5.3 Aufwand und Laufzeit
Zeit je Standpunkt (Aufnahme → veröffentlichte Szene) über die drei Geräteklassen;
Rechenzeit je Schritt; Grad der Automatisierung (manuelle Eingriffe).
Gemessen bislang nur der Rechenteil: Stitching 14,6 s, Reprojektion 2,1 s je
Panorama (2048×1024, 6–8 Eingangsbilder, Consumer-CPU).

## 5.4 Nutzbarkeit
Kurzer, strukturierter Nutzbarkeitstest (Aufgaben, Erfolg/Zeit, SUS-Fragebogen)
mit fachfremden Teilnehmenden über die GUI. **Offen.**

## 5.3 Aufwand und Laufzeit
Zeit je Standpunkt (Aufnahme → veröffentlichte Szene) über die drei Geräteklassen;
Rechenzeit je Schritt; Grad der Automatisierung (manuelle Eingriffe).

## 5.4 Nutzbarkeit
Kurzer, strukturierter Nutzbarkeitstest (Aufgaben, Erfolg/Zeit, SUS-Fragebogen)
mit fachfremden Teilnehmenden über die GUI.

# 6. Beispiel-Datensätze (frei verwendbar)

- **Renon (ICOS IT-Ren)** — E57 mit 6 Pinhole-Bildern (2048²) **+ Posen** je
  Standpunkt, CC-BY-4.0. Realer „Scanner-RGB"-Fall; belegt beide Ausgaben
  (Panorama + Inventur).
- **Poly Haven** — CC0-Equirektangular-Panoramen (u. a. Wald) für Viewer-Demo und
  als Ground-Truth der synthetischen Fisheye-Evaluation.
- **Consumer-Geräte** (Ricoh Theta / Insta360): Hersteller-Sample-Dual-Fisheye
  (Lizenz je Datei prüfen).

# 7. Software- und Datenverfügbarkeit

- Quellcode: öffentliches Git-Repository (For3Dsuite), OSI-Lizenz.
- Container: Dockerfile/Compose im Repo; ein Befehl reproduziert den Stack.
- Beispiel-Daten: Renon (CC-BY-4.0), Poly Haven (CC0).
- Lizenzen der Bausteine: Hugin (GPL), Pannellum (MIT), GIMP (GPL),
  Caddy (Apache-2.0), Garage (AGPL) — alle FOSS. Copyleft der GPL-Werkzeuge greift
  nicht auf die *Ergebnisbilder* (werden nur aufgerufen, nicht gelinkt).

# 8. Limitierungen (ehrlich)

- Stitching bleibt bei starker Parallaxe/Naharbeit fehleranfällig (physikbedingt).
- Reprojektion ist nur so gut wie die im E57 gespeicherten Posen/Kalibrierung.
- Wald ist ein schwerer Meshing-Fall — die Kette liefert Panorama+Punktwolke, kein
  fotoreales Mesh (dafür wäre 3D Gaussian Splatting die passendere Repräsentation).
- Nutzbarkeitstest mit kleiner Stichprobe; keine Verallgemeinerung auf alle Geräte.

# 9. Ausblick

- ~~Fisheye-Reprojektor + Stitching-Vergleich als Evaluations-Modul.~~ **Umgesetzt**
  (Abschnitt 5), einschließlich bilinearer Abtastung und Nahtversatz-Messung.
  Offen bleibt: die Evaluation um **echte Aufnahmen mit Nodalpunktversatz**
  erweitern (bisher nur parallaxenfreie synthetische Bilder) und den
  Nahtversatz-Schwellwert als Qualitätsflag in die GUI hängen.
- Anbindung weiterer Repräsentationen (3DGS-Szene, Mesh) im selben Viewer.
- Automatische Qualitätsflags (Nahtversatz, Belichtungssprünge) in der GUI.

# Referenzen

## Verwendete Software (mit im Projekt eingesetzten Versionen)

- **Hugin/Panotools** 2024.0.1 — Panorama-Stitching (GPL-2.0).
  <https://hugin.sourceforge.io/> · verwendet: `pto_gen`, `cpfind`, `cpclean`,
  `autooptimiser`, `pano_modify`, `nona`, `enblend`.
- **enblend/enfuse** (Teil der Hugin-Distribution) — Nahtüberblendung.
- **Pannellum** 2.5.6 — Web-Panorama-Viewer (MIT). Petroff, M. A. (2019):
  *Pannellum: a lightweight web-based panorama viewer.* Journal of Open Source
  Software 4(40), 1628. <https://doi.org/10.21105/joss.01628>
- **three.js** r160 — WebGL-Rendering für Punktwolke, QSM und 3DGS (MIT).
  <https://threejs.org/>
- **Leaflet** 1.9.4 — Übersichtskarte der Szenen (BSD-2-Clause).
- **Caddy** 2 (Alpine-Image) — Reverse Proxy mit automatischem TLS (Apache-2.0).
- **Garage** 1.0.1 — S3-kompatibler, self-hosted Objektspeicher (AGPL-3.0).
  <https://garagehq.deuxfleurs.fr/>
- **FastAPI** / **uvicorn** — HTTP-API und Job-Queue der Plattform (MIT/BSD).
- **NumPy** 1.26.4, **Pillow** 12.3.0, **OpenCV** 5.0.0, **laspy** 2.5.4 —
  Bild- und Punktwolkenverarbeitung, Metriken der Evaluation.
- **Docker** / **Compose** — reproduzierbare Gesamtumgebung.

## Formate und Standards

- **ASTM E2807-11** — *Standard Specification for 3D Imaging Data Exchange,
  Version 1.0* (E57-Format). ASTM International.
  Huber, D. (2011): *The ASTM E57 file format for 3D imaging data exchange.*
  Proc. SPIE 7864, Three-Dimensional Imaging, Interaction, and Measurement.
  <https://doi.org/10.1117/12.876555>
- **ASPRS LAS 1.4** — LiDAR-Punktwolkenformat.

## Bildqualitätsmaße der Evaluation

- Wang, Z., Bovik, A. C., Sheikh, H. R., Simoncelli, E. P. (2004): *Image quality
  assessment: from error visibility to structural similarity.* IEEE Transactions
  on Image Processing 13(4), 600–612. <https://doi.org/10.1109/TIP.2003.819861>
  — SSIM, hier eigenständig mit 11×11-Gaußfenster (σ = 1,5) implementiert.
- Kuglin, C. D., Hines, D. C. (1975): *The phase correlation image alignment
  method.* Proc. IEEE Int. Conf. on Cybernetics and Society, 163–165.
  — Grundlage der blockweisen Nahtversatz-Messung.

## Datensätze

- **Poly Haven** — CC0-HDRI/Panorama-Bibliothek; 11 Wald- und Gartenpanoramen
  (8192×4096) als Referenzwahrheit der Evaluation. <https://polyhaven.com/>
- **Renon / ICOS IT-Ren** — terrestrischer Laserscan (E57 mit 6 Pinhole-Bildern
  und Posen je Standpunkt), CC-BY-4.0. Realer „Scanner-RGB"-Fall.
- **SYSSIFOSS** — blatt/holz-getrennte TLS-Einzelbäume (RIEGL VZ-400),
  CC-BY-4.0. <https://doi.org/10.11588/DATA/UUMEDI>
- **SegmentedForests** — manuell semantisch gelabelte TLS/MLS-Waldwolken
  (MIT-Lizenz). Laino, D., Cabo, C., Ordóñez, C. et al. (2025):
  *SegmentedForests: a labelled dataset of terrestrial LiDAR point clouds for
  semantic segmentation of forests.* Forestry.
  <https://doi.org/10.1093/forestry/cpaf062> · Daten:
  <https://doi.org/10.5281/zenodo.17396681>

## Wald-/TLS-Verfahren (für den Fachdaten-Teil, Abschnitt 3.4)

- **3DFin / dendromatics** — Laino, D., Cabo, C., Prendes, C. et al. (2024):
  *3DFin: a software for automated 3D forest inventories from terrestrial point
  clouds.* Forestry 97(4). <https://doi.org/10.1093/forestry/cpae020>
- **FORTLS** — Molina-Valero, J. A. et al. (2022): *Operationalizing the use of
  TLS in forest inventories: the R package FORTLS.* Environmental Modelling &
  Software 150, 105337. <https://doi.org/10.1016/j.envsoft.2022.105337>
- **lidR** — Roussel, J.-R. et al. (2020): *lidR: An R package for analysis of
  Airborne Laser Scanning (ALS) data.* Remote Sensing of Environment 251, 112061.
  <https://doi.org/10.1016/j.rse.2020.112061>
- **CspStandSegmentation** — Frey, J., Schindler, Z. et al.: Kostenpfad-basierte
  Einzelbaumsegmentierung, Universität Freiburg.
- **TreeGrOSS / BWINPro** — Nordwestdeutsche Forstliche Versuchsanstalt (NW-FVA),
  GPLv3; Bonitätsfunktionen nach Nagel, J. (1999).
- **CSF-Bodenfilter** — Zhang, W. et al. (2016): *An easy-to-use airborne LiDAR
  data filtering method based on cloth simulation.* Remote Sensing 8(6), 501.
  <https://doi.org/10.3390/rs8060501>

> Hinweis: DOIs und Jahreszahlen sind vor der Einreichung gegen die
> Verlagsangaben zu prüfen; die Softwareversionen entsprechen dem Stand, mit dem
> die berichteten Zahlen erzeugt wurden.
