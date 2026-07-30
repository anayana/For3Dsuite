# Renon-combined: die volle Auswertungskette auf einer dichten TLS-Wolke

Szene: [`scene.html?id=renon-combined`](https://anayana.github.io/For3Dsuite/scene.html?id=renon-combined)

Vier registrierte terrestrische Scans (E57) am ICOS-Standort IT-Ren, 28,8 Mio
Rohpunkte. Auf dieser einen Wolke laufen **Stammdetektion, Einzelbaum-Segmentierung
(ITCD), BHD nach sechs Verfahren, QSM-Zylindermodell und Wachstumsprognose** — und
zwar so, dass jeder Schritt aus dem Rohdatum reproduzierbar ist.

## Was am Ende in der Szene steht

| | Wert |
|---|--:|
| Kernflaeche (r = 20 m) | 0,126 ha |
| Detektierte Staemme | 82 |
| Stammzahl | 652 /ha |
| Grundflaeche | 46,4 m²/ha |
| BHD Median / Max | 19,3 / 62,5 cm |
| Baumhoehe Median / Max | 21,3 / 28,0 m |
| Baeume mit BHD-Methodenvergleich | 56 |
| Baeume mit QSM | 60 (7.822 Zylinder) |
| Baeume mit TreeGrOSS-Prognose | 79 |

Stammzahl und Grundflaeche passen zur unabhaengig ausgewerteten Einzelscan-Szene
`renon-setup01` (dort 870 /ha, 48 m²/ha) — die Groessenordnung ist also nicht aus
einer einzelnen Detektion herausgefallen.

## Kette

```bash
O="27.99163650142562 -0.4348773085556139 0.26881917104222364"   # source.origin_xyz

# 1. Analyse-Wolke: 4 E57 verschmelzen, 1-cm-Voxel, Weltkoordinaten
python scripts/e57_merge.py "data/Renon/e57/"*.e57 --out data/Renon/_analysis.npz --voxel 0.01

# 2. Stammdetektion (Kreisfit an der Brusthoehen-Scheibe)
python scripts/inventory_from_cloud.py data/Renon/_analysis.npz data/Renon/trees_combined.csv \
    --origin $O --radius 30 --core-radius 20 --min-points 60 --arc-min 100 --rms-max 3

# 3. BHD nach mehreren Verfahren (+ 3DFin, zwei Parametersaetze)
python scripts/dbh_methods.py data/Renon/_analysis.npz data/Renon/trees_combined.csv \
    --out data/Renon/dbh_methods_combined.csv --summary data/Renon/dbh_methods_combined.json \
    --origin $O --radius 22 --stem-radius 0.8

# 4. ITCD: kuerzeste Wege im Punktgraphen; faerbt auch die Web-Bins ein
python scripts/itcd_cloud.py data/Renon/_analysis.npz data/Renon/trees_combined.csv \
    --out data/Renon/itcd_combined.npz --crowns data/Renon/crowns_combined.csv \
    --scene platform/dev-data/media/scenes/renon-combined/scene.json --origin $O --radius 22

# 5. QSM je Baum (Schafttaper + Astskelett)
python scripts/qsm_cloud.py data/Renon/_analysis.npz data/Renon/itcd_combined.npz \
    --stems data/Renon/trees_combined.csv --out data/Renon/qsm_combined --origin $O --radius 22

# 6. Marker bauen und mit allem anreichern
python scripts/markers_from_xyz.py data/Renon/trees_combined.csv \
    --scene platform/dev-data/media/scenes/renon-combined/scene.json
python scripts/scene_enrich_trees.py platform/dev-data/media/scenes/renon-combined/scene.json \
    --dbh data/Renon/dbh_methods_combined.csv --crowns data/Renon/crowns_combined.csv \
    --qsm data/Renon/qsm_combined.json
cp data/Renon/qsm_combined.bin platform/dev-data/media/scenes/renon-combined/qsm.bin

# 7. Prognose mit der ECHTEN TreeGrOSS-Engine (Dienst muss laufen, s. growth-service/)
python scripts/treegross_export.py export --scene <scene.json> --out data/Renon/_tg_trees.json \
    --default-species "Picea abies" --area-ha 0.1257 --age 200 --site-index 32 --years 30 --step 10
curl -s -X POST localhost:8362/simulate -H "Content-Type: application/json" \
     -d @data/Renon/_tg_trees.json > data/Renon/_tg_future.json
python scripts/treegross_export.py import --result data/Renon/_tg_future.json \
    --scene <scene.json> --year 2056 --attach-key prognosis

python platform/dev/export_static.py
```

## BHD: sechs Verfahren, aber keine Genauigkeitsaussage

Das ist der wichtigste Unterschied zum [SYSSIFOSS-Benchmark](BENCH_DBH.md): dort gibt
es eine **Feld-Inventur**, hier nicht. Messbar ist deshalb nur die **Uebereinstimmung**
der Verfahren (Praezision), nicht die Genauigkeit — sie koennen gemeinsam falsch
liegen. Genau so ist es in der Szene beschriftet.

Konsens = Median der vier Verfahren, die an praktisch jedem Stamm rechnen; `3dfin`
und `QSM` bringen eine eigene Detektion bzw. ein eigenes Modell mit und werden
**dagegen gehalten**, statt den Konsens mitzubilden.

| Verfahren | im Konsens | n | Bias | mittlere \|Abw\| |
|---|:-:|--:|--:|--:|
| Kreisfit (Kasa, algebraisch) | ja | 22 | −1,47 | 1,50 cm |
| Kreisfit (geometrisch) | ja | 22 | +0,62 | 0,83 cm |
| RANSAC-Kreisfit | ja | 22 | +0,83 | 1,70 cm |
| Zylinderfit 3D (mit Achsneigung) | ja | 22 | +0,01 | 0,81 cm |
| 3DFin (dendromatics) | **nein** | 4 | +1,95 | 3,05 cm |
| QSM-Schafttaper | **nein** | 19 | −2,04 | 3,74 cm |

Median-Spanne der Konsens-Verfahren: **2,2 cm** (an 22 von 82 Staemmen mit guter
Datenlage bewertet).

**Befunde:**

* Die vier Scheiben-Verfahren stimmen auf **1–2 cm** ueberein. Das ist keine
  Selbstverstaendlichkeit, sondern das Ergebnis der Vorverarbeitung — ohne saubere
  Trennung des Einzelstammes lagen dieselben Verfahren 29 cm auseinander (s. u.).
* Die beiden **unabhaengigen** Verfahren liegen mit 3 cm mittlerer Abweichung
  daneben — beide ohne Zugriff auf unsere Detektion. Das ist die belastbarste
  Aussage dieses Vergleichs.
* **3DFin liefert in seiner Voreinstellung nur an 4 von 82 Staemmen einen BHD**
  (37 Staemme detektiert, davon 33 ohne akzeptierten Durchmesser). Grund ist eine
  Guetepruefung, die 9 von 16 Umfangssektoren fordert — **202 Grad Abdeckung**,
  waehrend dieser Bestand im Median nur **190 Grad** hergibt. Mit auf 7 Sektoren
  gesenkter Forderung werden es 8. Beide Laeufe stehen in
  `data/Renon/dbh_methods_combined.json`.
* **Verworfen: Umfang der konvexen Huelle / π** (das Analogon zum Massband der
  Feldinventur). Es braucht eine geschlossene, duenne Mantellinie; hier fehlt beides.
  Gemessen ueberschaetzte es um +10 cm an n = 5 — als Verfahren im Vergleich waere
  das irrefuehrend.

## Drei Fehler, die still falsche Zahlen erzeugt haben

Alle drei sahen nach plausiblen Ergebnissen aus, keiner hat eine Warnung geworfen —
sie stehen hier, weil sie sich beim naechsten Datensatz wiederholen werden.

1. **Verschmolzene Nachbarstaemme.** Ein 0,8-m-Umkreis um eine Brusthoehen-Scheibe
   enthaelt bei 650 Staemmen/ha regelmaessig den Nachbarn. Zusammenhangskomponenten
   allein trennen ihn nicht (bei 1-cm-Wolke und 4-cm-Raster verschmelzen zwei Staemme,
   deren Rinde sich auf 6 cm naehert). Ergebnis: ein „Stamm" mit **112 cm BHD** in
   einem Bestand, dessen groesster gepruefter Stamm 62,5 cm hat — und alle Verfahren
   waren sich einig. Loesung: `stem_shell()` schneidet die Mantelschale um die
   Stammachse anhand des **Modus des Abstandshistogramms** heraus (ohne Kreisfit,
   also ohne das Ergebnis vorwegzunehmen), plus Plausibilitaetsvergleich mit der
   Detektion. 26 Staemme gelten seitdem als *unsicher* und werden **ohne Zahl**
   veroeffentlicht, statt mit einer falschen.
2. **Holzfilter am falschen Merkmal.** Die Oberflaeche eines 62-cm-Stammes ist im
   12-cm-Umfeld eine **Ebene**, keine Linie. Ein Linearitaetsfilter `(l1−l2)/l1`
   wirft damit genau den Stamm weg und behaelt die Zweige: das QSM folgte einem Ast
   nach oben und meldete **6,6 cm BHD** an einem 62-cm-Stamm. Richtig ist die
   Kugelform `l3/l1` — klein an jeder Holzoberflaeche (Ebene *oder* Linie), gross im
   Nadelbueschel.
3. **Unbeschraenkter geometrischer Kreisfit.** An zwei Staemmen erklaerte der Solver
   die 16 cm dicke Trennschale als *einen* riesigen Kreis, der sie tangential
   durchlaeuft: 121 statt 20 cm, 131 statt 25 cm. Beides sind gueltige Minima des
   Abstandsmasses — verboten sind sie nicht durch die Mathematik, sondern durch die
   Geometrie. Seitdem sind Zentrum (±30 cm) und Radius beschraenkt, und ein Fit an
   der Grenze faellt weg.

## ITCD: kuerzeste Wege statt Luftlinie

`segment_itcd.py` ordnet jeden Punkt dem in der Draufsicht naechsten Stamm zu — das
schneidet gerade Grenzen durch verzahnte Kronen. `itcd_cloud.py` nimmt stattdessen
die Entfernung **entlang des Holzes**: Voxelgraph (8 cm), ein Dijkstra-Lauf von einem
virtuellen Startknoten auf alle Saatvoxel, Zuordnung anschliessend aus dem
Vorgaengerbaum per Pointer-Jumping. Waagerechte Kanten sind um den Faktor 3
verteuert — den eigenen Schaft hoch ist naeher als quer durch die Unterschicht in die
Nachbarkrone.

Ergebnis: **12,0 von 13,6 Mio Vegetationspunkten zugeordnet (88 %)**, 80 der 82
Staemme getroffen, 59 mit ableitbarem Kronenansatz.

**Grenzen.** Die Punktzahl je Baum schwankt extrem (Median 508.000 innerhalb 5 m,
14.000 bei 15–20 m) — das ist **Scandichte**, nicht Zuordnungsqualitaet: sie faellt
mit dem Abstandsquadrat zum Standpunkt. An 8 Staemmen (10 %) ordnet das Verfahren
fast nichts zu, meist unterstaendige Staemme direkt neben einem herrschenden Nachbarn.
Der **Kronendurchmesser** ist die Huelle der zugeordneten Punkte und dort, wo die
Segmentierung zu viel zuschlaegt, eine **Obergrenze** (am dominanten Baum 01 mit
11,4 m deutlich zu weit fuer eine Fichte).

## QSM ohne annotierte Blatt-Holz-Trennung

`qsm_tree.R` (aRchi) setzt die **manuell annotierte** Blatt-Holz-Trennung von
SYSSIFOSS voraus — das Modell startet dort auf gemessener Wahrheit. Fuer Renon gibt
es die nicht, und aRchi ist aus CRAN archiviert (auf diesem Rechner laeuft ausserdem
kein R). `qsm_cloud.py` ist deshalb ein eigenes Python-Modell:

* **Schaft** explizit an der detektierten Position: je 0,5-m-Schicht ein Kreisfit auf
  der Mantelschale, die Achse wandert mit — ergibt eine **Taperkurve** und damit
  Schaftvolumen **ohne Formfaktor**. (Beispiel Baum 01: 72,2 cm am Fuss → 66,0 bei
  1,25 m → 56,0 bei 5,75 m; Schaftvolumen 4.497 l gegen 4.158 l aus der
  Formfaktor-Naeherung der Inventur.)
* **Aeste** aus dem Wegeskelett: Ringe konstanter Pfadlaenge, darin
  Zusammenhangskomponenten als Querschnitte; Ordnung steigt am Abzweig, nicht an der
  Fortsetzung.
* Ausgabe im Format, das der Viewer schon kennt (float32 Start/Ende/Radius + uint8
  Ordnung), damit „QSM-Modell" und die Segment-Klicks ohne Aenderung funktionieren.

**Das Kronenholzvolumen ist eine Obergrenze.** Der Holzfilter ist eine
Geometrie-Heuristik; Nadeln, die als Holz durchgehen, treiben die Radien feiner Zweige
nach oben. Verdeckte Kronenteile fehlen ganz und wirken gegenlaeufig. Schaft und
QSM-BHD stammen aus Kreisfits am dicht gescannten Stamm und sind belastbarer — was
sie wert sind, zeigt die Zeile „QSM-Schafttaper" in der Tabelle oben.

## Prognose: echte TreeGrOSS-Engine

Kein Stub: `GET /health` meldet `engine: treegross`, der Lauf ueber 79 Baeume und
30 Jahre braucht 0,55 s (HTTP 200). Mittlerer BHD **27,7 → 30,3 cm**, mittlere Hoehe
**21,8 → 22,0 m** in 30 Jahren.

Der fast fehlende Hoehenzuwachs ist **Modellverhalten, kein Konfigurationsfehler**:
bei Bestandesalter 200 Jahren und dieser Dichte reagiert TreeGrOSS so (in
`growth-service/README.md` gegen 60/120/200 Jahre durchgerechnet). Der Stub haette
artdifferenziert +12 cm BHD und +7,5 m Hoehe geliefert — die Zahlen belegen also
mit, dass die GPL-Engine antwortet.

**Vorbehalte, die in der Szene stehen:** Bonitaet 32 und Alter 200 sind Annahmen
(`data/Renon/STANDORT.md`), Fichte ist fuer alle Staemme angenommen (die Marker
tragen keine Art), und TreeGrOSS ist auf **Feld**-BHD kalibriert — LiDAR-BHD hat eine
andere Fehlerstruktur.
