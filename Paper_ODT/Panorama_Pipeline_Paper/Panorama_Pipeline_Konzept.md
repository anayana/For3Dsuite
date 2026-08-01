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

# 2. Verwandte Arbeiten und Abgrenzung

## 2.1 Panorama-Stitching

Das automatische Zusammensetzen überlappender Aufnahmen zu einem Panorama gilt
seit Brown & Lowe (2007) als weitgehend gelöst: invariante Merkmale (SIFT),
paarweise Registrierung, Bündelausgleich und Multiband-Blending. Szeliski (2006)
fasst das Feld zusammen. Die freie Referenzimplementierung ist
**Hugin/Panotools**, dessen Kommandozeilenwerkzeuge (`cpfind`, `autooptimiser`,
`nona`, `enblend`) auch in dieser Arbeit den Stitching-Zweig bilden. Der
verbleibende, physikalisch bedingte Fehler ist die **Parallaxe**: nur bei
Rotation um den Nodalpunkt sind die Aufnahmen exakt konsistent.

## 2.2 Web-basierte Darstellung

Für Panoramen im Browser sind **Pannellum** (Petroff 2019) und Marzipano
etabliert, für große Punktwolken **Potree** (Schütz 2016), das auf three.js
aufsetzt und Millionen Punkte ohne Plugin darstellt. Beide Stränge existieren
unabhängig voneinander; die vorliegende Arbeit koppelt sie in einer Szene
(Pannellum für das Panorama, eine eigene three.js-Ansicht für Punktwolke, QSM
und Marker), damit dieselbe Aufnahme in beiden Repräsentationen begehbar ist.

## 2.3 Sphärische Bilder terrestrischer Laserscanner

Terrestrische Laserscanner tasten ihre Umgebung **sphärisch** ab; die Kugel muss
für eine 2D-Darstellung projiziert werden, wobei die Projektionswahl messbar auf
nachgelagerte Verfahren wirkt (Vergleich verschiedener Projektionen für die
merkmalsbasierte Registrierung, Wang et al. 2015). Panoramische Intensitäts- und
Reflektanzbilder werden für die **automatische Registrierung** von Standpunkten
genutzt (Kang et al. 2009), projizierte Panoramaaufnahmen dienen als Eingang für
die **semantische Segmentierung** mit 2D-Netzen.

Das ist der Punkt der Abgrenzung: In dieser Literatur ist das sphärische
Scannerbild durchweg ein **Zwischenprodukt** — Mittel zur Registrierung, zur
Segmentierung oder zum Einfärben der Punktwolke. Als **begehbares Endprodukt**,
das zugleich abgeleitete Fachdaten trägt, wird es selten weiterverwertet, obwohl
Pose und Kalibrierung im E57-Container bereits mitgeliefert werden und die
Reprojektion damit ohne Kontrollpunkte auskommt.

## 2.4 Forstliche Auswertung terrestrischer Punktwolken

Die Ableitung von Bestandesgrößen aus TLS ist ein eigenes, reifes Feld:
**lidR** (Roussel et al. 2020) als allgemeine Verarbeitungsumgebung,
**CspStandSegmentation** (Frey & Schindler) für die Einzelbaumsegmentierung und
**3DFin** (Laino et al. 2024) für die automatische Stammdetektion und BHD-Messung. Diese Arbeit
entwickelt hier bewusst **nichts Neues**, sondern bindet die etablierten
Werkzeuge ein — und berichtet in Abschnitt 3.4 offen, dass 3DFin der zunächst
implementierten eigenen Baseline deutlich überlegen ist.

## 2.5 Abgrenzung (ehrlich)

Neu ist **kein Einzelbaustein**. Stitching, Web-Viewer, TLS-Inventur und
Objektspeicher sind je für sich Stand der Technik. Der Beitrag liegt in drei
Punkten:

1. **Vereinigung beider Eingangsklassen in einer Kette**, mit automatischer
   Fallunterscheidung an den Daten statt einer Nutzereingabe (Abschnitt 3.1) —
   und mit einer Messung, was die posen-bekannte Reprojektion gegenüber dem
   Stitching tatsächlich einbringt (Abschnitt 5).
2. **Weiterverwertung der Scanner-RGB-Bilder als begehbares Endprodukt**, das
   die aus derselben Wolke abgeleiteten Inventurdaten trägt.
3. **Reproduzierbarkeit und Datensouveränität**: containerisiert, self-hostbar,
   mit offen lizenzierten Beispieldaten und im Repository hinterlegten
   Evaluations-Rohdaten.

„Das wird nie gemacht" wäre zu stark: einzelne kommerzielle Scanner-Suiten
exportieren Panoramen, und Web-Viewer für Punktwolken sind verbreitet. Die
Behauptung ist enger — eine **offene, containerisierte, herstellerunabhängige**
Kette, die beide Eingangsklassen automatisch behandelt und das Ergebnis mit
Fachdaten verknüpft, ist uns nicht bekannt.

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

Aus derselben Punktwolke abgeleitete Inventur — Stammdetektion, BHD, Höhe,
Kronenmetriken, QSM (Zylindermodell) und Wachstumsprognose — wird als
**georeferenzierte Marker** in die begehbare Szene gelegt: Panorama und
Datenträger in einem. Die Kette ist kein Demonstrator, sondern gegen
Ground Truth geprüft.

**Stammdetektion gegen semantisch gelabelte Wolken.** Auf zwei TLS-Plots des
SegmentedForests-Datensatzes, in denen jeder Punkt manuell klassiert ist, lässt
sich erstmals *Genauigkeit* statt bloßer Übereinstimmung messen:

| Verfahren | plot_06 (68 Stämme) | plot_07 (128 Stämme) |
|---|--:|--:|
| eigene numpy-Baseline | 60,3 % / 42,3 % | 34,4 % / 74,6 % |
| + Schaftkontrolle | 57,4 % / 70,9 % | — |
| lidR (Eigenbau) | 66,2 % / 45,9 % | — |
| CspStandSegmentation | 57,4 % / 27,7 % | — |
| **3DFin** (Konfiguration der Autoren) | **98,5 % / 95,7 %** | **94,5 % / 100 %** |

(Recall / Precision; Treffer = Detektion ≤ 0,6 m vom Referenzstamm.)

Der Befund ist für die Suite folgenreich und wird hier offen berichtet: **das
etablierte Fachwerkzeug 3DFin ist der eigenen Baseline deutlich überlegen**, über
beide Plots stabil. Die Kette setzt es deshalb auf plotweiten TLS-Wolken als
Detektor ein, statt es nur zu vergleichen. Weil der Datensatz auch Sträucher,
liegendes Totholz, Steine und Pfähle labelt, ist zudem belegbar, *worauf* die
Fehlalarme der schwächeren Verfahren sitzen — bei der Baseline auf plot_06 zu
50 % auf Strauch- und Bodenvegetation.

**Reichweite.** Die Überlegenheit gilt für plotweite Wolken mit ausreichender
Umfangsabdeckung. Am eigenen Renon-Bestand (Median 180° Bogen gegen 280–360° in
den Referenzplots) verweigert 3DFin an 29 von 37 Detektionen den Durchmesser —
korrektes Verhalten, denn die Daten tragen dort keinen. Ein Durchlauf über die
Bodenmodell-Auflösung ändert daran nichts; der Engpass ist die Abdeckung, nicht
die Konfiguration. Umgekehrt geben die eigenen Verfahren dort weiterhin Zahlen
aus, die dann auf 180°-Bögen ruhen — eine Aussage über die Aufnahme, nicht über
die Verfahren.

Methodik und Rohdaten: [`scripts/BENCH_DETECTION.md`](../../scripts/BENCH_DETECTION.md),
BHD-Genauigkeit gegen Feld-Inventur in [`scripts/BENCH_DBH.md`](../../scripts/BENCH_DBH.md).

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

**Zählweise (gilt im ganzen Abschnitt):** *durchgelaufen* heißt, die Kette hat
überhaupt ein Panorama geschrieben; *brauchbar* heißt zusätzlich, dass es
geometrisch korrekt ist. Der Unterschied ist beim Stitching wesentlich — zwei
Läufe liefern ein vollständiges, aber falsch registriertes Bild.

| Zweig | durchgelaufen | brauchbar | PSNR (dB) | SSIM | Nahtversatz (px) | Laufzeit |
|---|--:|--:|--:|--:|--:|--:|
| Stitching (Pose geschätzt) | 8 / 11 | **6 / 11** | 22,98 ± 2,74 | 0,837 ± 0,060 | 0,14 (p95 0,53) | 14,6 s |
| Reprojektion (Pose bekannt) | 11 / 11 | **11 / 11** | **26,87 ± 1,96** | **0,886 ± 0,039** | **0,10 (p95 0,23)** | 2,1 s |

Die Kennzahlen beziehen sich auf die *brauchbaren* Läufe; die beiden falsch
registrierten Stitches sind ausgenommen, weil ihre Werte (8,6 und 11,7 dB) sonst
Mittelwert und Streuung dominieren würden — sie sind unten separat ausgewiesen.

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

### Reale Aufnahmen: was Parallaxe tatsächlich kostet

Der Vorbehalt, dass die synthetischen Zahlen obere Schranken sind, lässt sich mit
freien Daten auflösen. `eval_seams.py` misst den Nahtversatz **ohne
Referenzpanorama**: `nona` remappt jede Aufnahme einzeln in die Panoramafläche,
und in den Überlappungen zeigen zwei Quellbilder dieselbe Blickrichtung — bei
perfekter Registrierung und Rotation um den Nodalpunkt müssten sie dort identisch
sein. Ihre lokale Verschiebung ist der Fehler.

Als reale Aufnahme dient **PASSTA LunchRoom** (Zenodo, CC-BY-4.0): 72 Fotos einer
rotierenden Canon EOS 70D mit mitgelieferter Kalibrierung. Als Gegenversuch werden
aus einem CC0-Panorama synthetische Aufnahmen mit **identischer Geometrie**
gerendert — 18 Positionen, 93,6° rektilinear, dieselbe Stitching-Kette, dieselbe
Panoramabreite. Der einzige Unterschied ist, dass die realen Aufnahmen echte
Parallaxe, Sensorrauschen und Belichtungsunterschiede enthalten:

| | synthetisch (parallaxenfrei) | real (rotierende Kamera) |
|---|--:|--:|
| Nahtversatz Median | **0,07 px** | **3,95 px** |
| p95 | 0,18 px | 24,78 px |
| Maximum | 0,48 px | 29,99 px |
| Blöcke über 1 px | 0,0 % | 67,5 % |

**Der Median liegt um den Faktor ~56 höher, das 95. Perzentil um ~140.** Damit ist
belegt, was zuvor nur behauptet werden konnte: die synthetische Evaluation
unterschätzt den realen Stitching-Fehler um Größenordnungen, und die dort
gemessene Lücke zwischen den beiden Zweigen ist eine **Untergrenze**.

*Einordnung.* PASSTA LunchRoom ist eine Innenraumszene mit nahen Objekten —
Parallaxe wirkt sich bei geringer Distanz am stärksten aus. Eine Außenaufnahme im
Bestand mit überwiegend weit entfernten Objekten fällt günstiger aus; die 3,95 px
sind also kein universeller Wert, sondern ein Beispiel für den ungünstigen Fall.
Ein Teil des Unterschieds geht zudem auf Rauschen und Belichtungsunterschiede
zurück, nicht allein auf Parallaxe. Der posen-basierte Zweig ist von alldem nicht
betroffen: dort gibt es keine Überlappungsnähte, weil jede Blickrichtung aus genau
einer Kamera stammt.

### Grenzen dieser Zahlen (wichtig)

- **Kein Parallaxenfehler in den PSNR/SSIM-Zahlen.** Alle synthetischen Aufnahmen
  teilen denselben Nodalpunkt; die Stitching-Werte in der Tabelle oben sind daher
  **obere Schranken**. Wie groß der Abstand zur Realität ist, misst der Abschnitt
  „Reale Aufnahmen" (Faktor ~56 im Median des Nahtversatzes).
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

## 5.3 Aufwand, Laufzeit und Automatisierungsgrad
Beide Zweige laufen **vollautomatisch, ohne manuelle Kontrollpunkte** — die
Stitching-Kette detektiert im Median 156 Kontrollpunkte je Panorama selbst
(`cpfind`/`autooptimiser`). Rechenzeit je Panorama (2048×1024, 6–8 Eingangs-
bilder, Consumer-CPU): Stitching Median 16 s, Reprojektion Median 5 s. Der
entscheidende Aufwandsunterschied ist nicht die Sekundenzahl, sondern die
**Robustheit ohne Nacharbeit**: der posen-basierte Zweig liefert 11/11 Szenen
ohne Eingriff, das Stitching 8/11 durchgelaufen und davon 6/11 brauchbar
(3 Abbrüche, 2 falsch registriert — Zählweise s. 5.1). Offen: die Wandzeit
*Aufnahme → veröffentlichte Szene* inkl. Feldaufwand über die drei Geräteklassen.

## 5.4 Nutzbarkeit
Kurzer, strukturierter Nutzbarkeitstest (Aufgaben, Erfolg/Zeit, SUS-Fragebogen)
mit fachfremden Teilnehmenden über die GUI. **Noch offen** (Protokoll steht,
Durchführung mit Teilnehmenden ausstehend).

# 6. Beispiel-Datensätze (frei verwendbar)

Alle berichteten Zahlen stammen aus offen lizenzierten Daten; nichts davon ist
synthetisch beschönigt oder nicht nachvollziehbar.

- **Poly Haven** — 11 CC0-Equirektangular-Panoramen (8192×4096) als
  **Ground Truth der Panorama-Evaluation** (Abschnitt 5) und für die Viewer-Demo.
- **Renon (ICOS IT-Ren)** — E57 mit 6 Pinhole-Bildern (2048²) **+ Posen** je
  Standpunkt, CC-BY-4.0. Realer „Scanner-RGB"-Fall; belegt beide Ausgaben
  (Panorama + Inventur) und dient als Beispiel für eine Wolke mit *unzureichender*
  Umfangsabdeckung.
- **SegmentedForests** — zwei TLS-Plots (Wienerwald) mit **manuell klassierten
  Punkten**, MIT-Lizenz. Ground Truth der Detektionsprüfung in Abschnitt 3.4.
- **SYSSIFOSS** — blatt/holz-getrennte TLS-Einzelbäume mit unabhängiger
  **Feld-Inventur**, CC-BY-4.0. Ground Truth der BHD-Genauigkeit.
- **PASSTA LunchRoom** — 72 reale Aufnahmen einer rotierenden DSLR mit
  Kalibrierung, CC-BY-4.0 (Zenodo 10.5281/zenodo.19663081). Belegt den realen
  Parallaxenfehler des Stitching-Zweigs.

> **Nicht enthalten:** Aufnahmen einer Consumer-360°-Kamera (Ricoh Theta,
> Insta360). Der reale Parallaxenfehler ist über PASSTA belegt, allerdings an
> einer Innenraumszene mit nahen Objekten und mit rektilinearem statt
> Fisheye-Objektiv.

# 7. Software- und Datenverfügbarkeit

- Quellcode: öffentliches Git-Repository (For3Dsuite), OSI-Lizenz.
- **Zwei Container-Stacks, beide lauffähig geprüft:**
  `docker/compose.yml` — Verarbeitungskette + statischer Viewer; der Einstiegspunkt
  `check` führt eine Offline-Reproduktion auf mitgelieferten Daten aus und endet
  mit Fehlercode, wenn das Ergebnis unplausibel ist (CI-tauglich).
  `platform/docker-compose.yml` — Self-Hosting mit Caddy, Garage und der API;
  Ende-zu-Ende geprüft (Upload → Job → veröffentlichte Szene → Medien direkt aus
  dem Objektspeicher, an der Anwendung vorbei).
- Beispiel-Daten: Poly Haven (CC0), Renon (CC-BY-4.0), SegmentedForests (MIT),
  SYSSIFOSS (CC-BY-4.0) — Details in Abschnitt 6.
- Evaluations-Rohdaten im Repo: `data/_eval/ergebnisse.csv` (Panorama-Evaluation),
  `bench_dbh_results.csv` und `bench_detection_results.csv` (Fachdaten), dazu die
  Skripte, die sie erzeugen.
- Lizenzen der Bausteine: Hugin (GPL-2.0), Pannellum (MIT), three.js (MIT),
  Caddy (Apache-2.0), Garage (AGPL-3.0), FastAPI (MIT) — alle FOSS. Der Copyleft
  der GPL-Werkzeuge greift nicht auf die *Ergebnisbilder*, weil sie als Prozesse
  aufgerufen und nicht gelinkt werden. Der Wachstumsdienst (TreeGrOSS, GPLv3) ist
  aus demselben Grund als eigener Prozess hinter einer HTTP-Schnittstelle
  isoliert.

# 8. Limitierungen (ehrlich)

- Stitching bleibt bei starker Parallaxe/Naharbeit fehleranfällig (physikbedingt).
- Reprojektion ist nur so gut wie die im E57 gespeicherten Posen/Kalibrierung.
- Wald ist ein schwerer Meshing-Fall — die Kette liefert Panorama+Punktwolke, kein
  fotoreales Mesh (dafür wäre 3D Gaussian Splatting die passendere Repräsentation).
- **Die PSNR/SSIM-Zahlen stammen aus synthetischen Aufnahmen** ohne
  Nodalpunktversatz, Rauschen und Belichtungsunterschiede. Der reale Aufschlag ist
  über den referenzfreien Nahtversatz an PASSTA belegt (Faktor ~56 im Median),
  allerdings an einer Innenraumszene — für Bestandesaufnahmen im Freien mit
  weiter entfernten Objekten dürfte er geringer ausfallen. Eine reale
  Consumer-360°-Aufnahme fehlt weiterhin.
- Nutzbarkeitstest steht als Protokoll, ist aber noch nicht durchgeführt.

# 9. Ausblick

- ~~Fisheye-Reprojektor + Stitching-Vergleich als Evaluations-Modul.~~ **Umgesetzt**
  (Abschnitt 5), einschließlich bilinearer Abtastung und Nahtversatz-Messung.
  ~~Offen: echte Aufnahmen mit Nodalpunktversatz.~~ **Umgesetzt** über PASSTA und
  das referenzfreie Nahtmaß. Offen bleibt, den Nahtversatz-Schwellwert als
  Qualitätsflag in die GUI zu hängen und eine reale Consumer-360°-Aufnahme
  einzubeziehen.
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

## Panorama-Stitching und Darstellung

- Brown, M., Lowe, D. G. (2007): *Automatic panoramic image stitching using
  invariant features.* International Journal of Computer Vision 74(1), 59–73.
  <https://doi.org/10.1007/s11263-006-0002-3>
- Szeliski, R. (2006): *Image alignment and stitching: a tutorial.* Foundations
  and Trends in Computer Graphics and Vision 2(1), 1–104.
  <https://doi.org/10.1561/0600000009>
- Schütz, M. (2016): *Potree: Rendering large point clouds in web browsers.*
  Diplomarbeit, TU Wien. <https://www.cg.tuwien.ac.at/research/publications/2016/SCHUETZ-2016-POT/>

## Sphärische Bilder terrestrischer Laserscanner

- Wang, Y. et al. (2015): *A study of projections for key point based
  registration of panoramic terrestrial 3D laser scans.* Geo-spatial Information
  Science 18(1), 27–37. <https://doi.org/10.1080/10095020.2015.1017913>
- Kang, Z. et al. (2009): *Automatic registration of terrestrial laser scanning
  point clouds using panoramic reflectance images.* Sensors 9(4), 2621–2646.
  <https://doi.org/10.3390/s90402621>

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

- **PASSTA** — Meneghetti, G., Danelljan, M., Felsberg, M., Nordberg, K. (2015):
  *Image alignment for panorama stitching in sparsely structured environments.*
  Scandinavian Conference on Image Analysis (SCIA). Daten: CC-BY-4.0,
  <https://doi.org/10.5281/zenodo.19663081>

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
