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
und Nutzbarkeit über das Geräte-Spektrum. Über 11 CC0-Referenzpanoramen liefern
beide Zweige dort, wo Stitching gelingt, vergleichbare Genauigkeit (23,2 gegen
23,7 dB PSNR); entscheidend ist die Zuverlässigkeit: das posen-basierte Verfahren
rekonstruiert alle 11 Szenen, das Stitching scheitert an 5 von 11 — und ist dabei
siebenmal langsamer.

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

| Zweig | erfolgreich | PSNR (dB) | SSIM | Abdeckung | Laufzeit |
|---|--:|--:|--:|--:|--:|
| Stitching (Pose geschätzt) | **6 / 11** | 23,23 ± 2,52 | 0,839 ± 0,061 | 100,0 % | 14,6 s |
| Reprojektion (Pose bekannt) | **11 / 11** | 23,67 ± 2,20 | 0,794 ± 0,062 | 99,4 % | 2,1 s |

**Der Unterschied liegt nicht in der Genauigkeit, sondern in der Zuverlässigkeit.**
Wo Stitching gelingt, ist es gleichauf (23,2 gegen 23,7 dB) und im SSIM sogar
etwas besser — die Reprojektion verliert dort etwas, weil sie derzeit mit
Nächster-Nachbar-Abtastung arbeitet. Aber Stitching **scheitert an 5 von 11
Szenen**: dreimal bricht `enblend` ab (»excessive image overlap«, »degenerate
image/mask geometry«, »failed to detect any seam«), zweimal entsteht ein
geometrisch falsches Panorama (PSNR 8,7 bzw. 11,5 dB; auch unter erschöpfender
Suche über Drehung, Neigung und Spiegelung nicht besser als 11,7 dB — also kein
Mess-, sondern ein Registrierungsfehler). Die Reprojektion liefert an allen 11
Szenen ein Ergebnis, in einem Siebtel der Zeit.

Einzelwerte (PSNR dB, Stitching / Reprojektion): forest-slope 22,5/22,8 ·
furstenstein —/23,4 · hochsal —/21,0 · monks 24,9/25,2 · mossy 21,1/25,4 ·
nature-reserve 20,0/21,6 · niederwihl ✗/20,1 · quadrangle —/25,0 · sunset
24,0/24,5 · symmetrical-garden ✗/23,8 · woods 26,9/27,6.

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
  (Abschnitt 5). Offen bleibt: Nächster-Nachbar- durch bilineare Abtastung in
  `reproject_pano.py` ersetzen (kostet derzeit SSIM), Nahtversatz an den
  Überlappungen getrennt quantifizieren, und die Evaluation um echte Aufnahmen
  mit Nodalpunktversatz erweitern.
- Anbindung weiterer Repräsentationen (3DGS-Szene, Mesh) im selben Viewer.
- Automatische Qualitätsflags (Nahtversatz, Belichtungssprünge) in der GUI.

# Referenzen (Auswahl, zu vervollständigen)

- Hugin/Panotools — panorama stitching (FOSS).
- Petroff, M. — Pannellum (MIT).
- three.js — WebGL rendering library.
- ASTM E2807 / E57 — 3D imaging data exchange format.
- Poly Haven — CC0 HDRI/panorama library.
- (Wald-Anwendung) einschlägige TLS-Inventur- und QSM-Literatur.
