# Versuchsplan Paper C — Stammdetektion und BHD in Abhängigkeit von der Umfangsabdeckung

Stand 13.10.2026 · Entwurf zur Bestätigung · noch nichts gerechnet

**Forschungsfrage:** Ab welchem Abdeckungsbogen in Brusthöhe (und welcher Punktzahl je
Scheibe) liefern Detektoren und BHD-Verfahren verlässliche Ergebnisse?

**Schwerpunkt (nach Literaturabgleich):** BHD-Fehler und Ausfallrate **als Funktion des
Bogens, je Verfahren** (Kreisfit, RANSAC, Zylinder, GeoFit, 3DFin-Annahmeregel) → daraus
eine Qualitätsregel „ab welchem Bogen ist ein BHD vertrauenswürdig“. Scan-Design ist gut
untersucht (u. a. Li et al., IEEE TGRS, HELIOS-Simulation; Remote Sens. 11(13):1602) und
bleibt hier **nur Folgerung** (ein Abschnitt), nicht Hauptbeitrag. Volltexte zur Abgrenzung
noch nötig (vom Nutzer, arXiv/ScienceDirect hier gesperrt).

## 1. Szenen

| ID | Inhalt | Wahrheit | Zweck |
|---|---|---|---|
| **S1** | Prozedurale Bäume (`helios_scene.py`), Plot 40 × 40 m (≈ Größe plot_06/07) | Position + BHD exakt gesetzt | Hauptexperiment |
| S1-a/b/c | Dichte 400 / 800 / 1200 N/ha; BHD-Verteilung aus den Referenzstämmen plot_06/07 bzw. Renon `trees_setup001.csv` (87 Bäume) | | Verdeckung als Störgröße |
| **S2** | Wie S1, aber Stämme aus QSM-Zylindern (Wytham, CC BY 4.0): Krümmung, Neigung, Unrundheit | BHD aus QSM bei 1,3 m | Realistischere Geometrie |

Nötige Erweiterungen an `helios_scene.py` (klein):
1. Seed + Positionsgenerator (Poisson/geklumpt), statt nur Inventur-CSV.
2. Stamm optional elliptisch (Achsenverhältnis 0,85–1,0) + Rindenrauheit (Radiusrauschen ±3 mm).
3. Wahrheitstabelle `truth.csv` (id, x, y, BHD_cm) schreiben.
4. Mehr Zylindersegmente (10 → 32), sonst misst man die Facetten.

Unterwuchs/Totholz als Fehlalarmquelle: **nicht** in S1 (Precision wird dort nur
durch Kronen/Äste geprüft); dafür ist die Gegenprobe auf SegmentedForests da.

## 2. Scan-Konfigurationen

**Rechentrick:** Standpunkte sind unabhängig. Je Szene wird ein **Pool** einzeln
simuliert, Konfigurationen sind dann nur Teilmengen (Zusammenfügen offline, kein
Neurechnen).

- Pool je Szene: 5 × 5-Raster (Abstand 8 m) + 15 Zufallspunkte = **40 Standpunkte**.
- Konfigurationen: n = 1, 2, 3, 4, 6, 9 Standpunkte ×
  - Raster (regelmäßig verteilt),
  - Zufall (10 Ziehungen je n),
  - „eng" wie Renon (n Standpunkte innerhalb r ≤ 8 m).
- Scanner: `riegl_vz400` (HELIOS++-Standard), Höhe 1,5 m, Auflösung 0,06° (eine
  Stufe; Punktdichte wirkt zusätzlich über Entfernung Scanner–Stamm).

## 3. Kennzahlen

Je Stamm (Brusthöhe 1,3 m, Scheibe ± 5 cm):
- **Abdeckungsbogen** (16 Sektoren à 22,5°, wie 3DFin; zusätzlich 10°-Histogramm
  wie `inventory_from_cloud.py`), **Punkte je Scheibe**, Entfernung zum nächsten Standpunkt.

Je Verfahren, aufgetragen über Bogenklassen (0–360° in 45°-Schritten):
- Detektion: **Recall, Precision** (Match ≤ 0,6 m, wie `validate_detection_gt.py`).
- BHD: **Bias, RMSE, MAE** (cm), **Ausfallrate** (kein BHD geliefert).
- Schwelle je Verfahren = kleinster Bogen, ab dem Recall ≥ 90 % **und**
  RMSE ≤ 2 cm (Schwellenwerte vorläufig; aus Literatur festzulegen).
- Zusätzlich logistisches Modell P(Detektion) ~ Bogen + log(Punkte) + Dichte.

Verfahren: Baseline `inventory_from_cloud.py` (± `stem_continuity`), 3DFin
(Autoren-INI; Variante mit 7 statt 9 Sektoren), BHD: `kreisfit`, `geofit`,
`ransac`, `zylinder` (`dbh_methods.py`). lidR/CSP nur, wenn R verfügbar
(in der Cloud-Umgebung nicht installiert).

Weitere Verfahren (Kandidaten, Verfügbarkeit offen):
- **FORTLS** (R, Molina-Valero et al. 2022, Environ. Model. Softw. 150:105337): Bestandsschätzung aus
  Einzelscans mit Verdeckungskorrektur — passt direkt zur Fragestellung. CRAN ist aus der Cloud gesperrt;
  Installation über GitHub-Quellen oder auf dem Windows-Rechner prüfen.
- **SimpleTree/SimpleForest** (Lehrstuhl Waldwachstum Freiburg; Hackenberg et al. 2015, Forests 6:4245):
  QSM-basierter BHD; läuft als CompuTree-Plugin unter Windows.
- **lidR** (R) über conda-forge installierbar (`r-lidr`).
- **Hough-Kreisfit** (u. a. WSL-Technical-Note, Voxel + Hough) und **robuster geometrischer Fit**
  (Huber/Tukey; vgl. ISPRS Archives XLVIII-4-W11-2024) — selbst implementierbar, in die Monte-Carlo-Rechnung aufnehmen.
- **TLS2trees** (Python, Methods Ecol. Evol. 2023) und **rayextract/raycloudtools** (CSIRO) — offen, Linux;
  eher Segmentierung/QSM, BHD-Genauigkeit nicht belegt.
- Nicht offen bzw. nur beschrieben: TU Dresden (Bienert/Maas, mit TreeMetrics), WSL-Voxel/Hough-Methode,
  LWF (Leica MS50, astfreie Schaftlänge mit TUM). SSCI (Ehbrecht/Seidel, Göttingen) misst Struktur, nicht BHD.

**Wichtigste Vorarbeit zur Verdeckung:** Abegg et al. 2017, *Forests* 8(6):184 (UZH/WSL):
„Tree Diameter Distribution and Scanner Location Impact on Occlusion“ — muss zitiert und abgegrenzt werden.

## 4. Gegenprobe auf echten Daten

| Daten | Vorgehen | Referenz |
|---|---|---|
| SegmentedForests plot_06/07 (MIT) | Stämme mit ≥ 300° Bogen: Sektoren gezielt entfernen → künstlich 90/135/180/225/270° | BHD aus voller Scheibe (kein Feld-BHD!) |
| SYSSIFOSS (CC BY 4.0) | dito an den 5 Bäumen mit Feld-BHD | Feld-BHD |
| Renon (CC BY 4.0) | gemessene Bögen einordnen: liegen 3DFin-Ausfälle unter der S1-Schwelle? | keine (Plausibilität) |

Prüft, ob die Schwellen aus S1/S2 auf echte Rinde/Äste übertragbar sind.

## 5. Rechenaufwand

- Simulation: 4 Szenen (S1-a/b/c, S2) × 40 Standpunkte = **160 HELIOS-Läufe**.
  Zeit je Lauf: **unbekannt** → zuerst Pilot (1 Szene, 1 Standpunkt) messen, dann hochrechnen.
- Auswertung: 4 Szenen × 6 n × (Raster 1 + eng 1 + Zufall 10) = **288 Wolken**
  × 6 Verfahren. 3DFin ist der teure Teil; Laufzeit ebenfalls im Pilot messen.
- Cloud-Umgebung hier: 4 Kerne, 15 GB RAM, **HELIOS++ und R fehlen**, zenodo gesperrt
  (SegmentedForests/Wytham nicht ladbar). Optionen ohne Kosten: (a) pyhelios hier per
  pip/conda installieren — ob das durch den Proxy geht, prüfe ich im Pilot;
  (b) Rechnung auf deinem Windows-Rechner (helios-Env existiert laut `helios_run.py`);
  (c) GitHub Actions (kostenlos nur bei öffentlichem Repo).

## 6. Veröffentlichungen (ohne Gebühr)

| Nr. | Was | Wo | Wann |
|---|---|---|---|
| C1 | Bogen-Fehler-Kurven je Verfahren, Qualitätsregel, Gegenprobe echte Daten (englisch) | *Forestry* → *EJFR* → *PFG* | zuerst |
| C2 | Praxisbeitrag: Scanplanung je Bestandstyp + Qualitätsprüfung nach dem Scan, mit Scanplaner (`scanplaner.html`) (deutsch) | *AFZ-DerWald*; Kurzfassung für *waldwissen.net* | nach Annahme von C1 |

- C2 erst nach C1: sonst Konflikt mit der Erstveröffentlichungs-Regel des Journals;
  C2 zitiert C1 und bringt keine neuen Ergebnisse.
- waldwissen.net publiziert über Partnerinstitute (FVA, LWF, BFW, WSL) — ob ein
  unabhängiger Autor direkt einreichen kann, ist ungeklärt → dort anfragen.
- Gebührenfreiheit des Abo-Wegs (keine Page/Colour Charges) **vor Einreichung auf der
  Journalseite prüfen** — von hier nicht prüfbar.
- Für C2 Bestandstypen des Scanplaners mit offenen Inventurdaten belegen
  (z. B. BWI für Mitteleuropa, IFN Portugal für Algarve) statt Richtwerten.

## 7. Reihenfolge

1. Pilot: HELIOS lauffähig machen, 1 Szene × 1 Standpunkt, Laufzeit messen.
2. `helios_scene.py` erweitern (Abschn. 1), Wahrheitstabelle.
3. Pool simulieren → Teilmengen → Kennzahlen (S1).
4. S2 (QSM-Stämme), Gegenprobe echte Daten.
5. Abbildungen, Manuskript C1.
6. Nach Annahme: Praxisbeitrag C2, Scanplaner mit belegten Schwellen und Bestandswerten.

## 8. Stand der Rechnung

- **13.10.2026 – Monte-Carlo, idealer Kreis** (`scripts/arc_error_mc.py`, `Paper_ODT/Forst_Benchmark_Paper/results/arc_error_mc.csv`;
  13 Bögen × σ 2/5/10 mm × N 50/200/1000 × BHD 20/40 cm, 300 Wiederholungen):
  Kasa-basierte Verfahren (kreisfit, ransac, zylinder) unterschätzen bei kurzen Bögen systematisch
  (BHD 40, σ 5 mm, N 200: −2,4 cm bei 90°, −7,1 cm bei 67,5°); der geometrische Fit bleibt
  unverzerrt und nahe der Cramér-Rao-Schranke. Schwelle RMSE ≤ 2 cm & |Bias| ≤ 1 cm: geofit 45–135°,
  übrige 90–180° (je nach σ, N, BHD) — **unter idealen Bedingungen deutlich unter 3DFins 202,5°**.
  Noch ohne Unrundheit, Ausreißer (Äste, Unterwuchs) und Registrierfehler → nächster Schritt.
- HELIOS++ 2.2.2 lauffähig in der Cloud (conda-forge über micromamba, `/opt/mm/root/envs/helios`).
- **Monte-Carlo mit Störungen** (`scripts/arc_error_mc_real.py`, `results/arc_error_mc_real.csv`;
  7 Szenarien × 13 Bögen × N 200/1000 × BHD 20/40 cm, σ 5 mm, 100 Wdh.; 6 Verfahren inkl. Hough mit
  Normalenvotum und Huber-robustem geometrischem Fit). Schwelle RMSE ≤ 2 cm & |Bias| ≤ 1 cm:
  - **Ausreißer (Äste/Unterwuchs, 5–15 %)**: Kasa, geofit, Zylinder erreichen die Schwelle **nie**, auch nicht
    bei 360° (RMSE 2–7 cm). RANSAC (mit 90°-Inlier-Bogen) ab 112,5–135°; Huber-robust erst ab 135–270°
    (versagt bei kurzen Bögen, weil der Kasa-Startwert verzerrt ist); Hough ab 180–225°.
  - **Unrunde Stämme** (Achsverhältnis 0,85–1): alle Verfahren brauchen bei BHD 40 cm **≈ 180–202,5°**;
    Teilsicht einer Ellipse verfälscht den Durchmesser systematisch. → stützt 3DFins 202,5°-Regel.
  - **Registrierversatz 5–10 mm**: kleiner Effekt (RMSE-Boden 0,5–0,9 cm), Schwellen kaum verändert.
  - **Kombiniert**: RANSAC 135–180°, Huber 180–225°, Hough 225–315° bzw. nie, übrige nie.
  - Zwischenfazit: Die nötige Abdeckung hängt stärker an der **Robustheit des Verfahrens** und der
    **Unrundheit** als am Bogen allein; eine feste Schwelle für alle Verfahren ist nicht begründbar.
- **Nebenbefund HELIOS-Pilot**: Sektorzählung (16 × 22,5°) bewertet eine echte Halbsicht (≤ 180°) oft als
  202,5–225° → 3DFins Regel lässt Einzelseitensicht durch. Wird in den HELIOS-Läufen mit `arc1_deg`
  (1°-Bins) quantifiziert.
