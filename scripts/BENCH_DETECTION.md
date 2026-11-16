# Stammdetektion gegen semantische Ground Truth

Erster Benchmark der Suite, der **Genauigkeit** misst statt Übereinstimmung.
Möglich wird das durch [SegmentedForests](https://doi.org/10.5281/zenodo.17396681)
(Laino, Cabo, Ordóñez et al., MIT-Lizenz, Aufsatz
[doi:10.1093/forestry/cpaf062](https://doi.org/10.1093/forestry/cpaf062)): dort ist
**jeder Punkt** manuell semantisch klassiert — Stamm, Äste+Blätter, Boden, Strauch,
liegendes Totholz, Stubben, Steine, Personen, Pfähle.

Bisher konnte die Suite nur zwei schwächere Fragen beantworten: ob Verfahren
*einer Meinung* sind (`dbh_methods.py` am Renon-Bestand, ohne Feldmaß) oder wie
genau der BHD an **fünf** Einzelbäumen ist ([`BENCH_DBH.md`](BENCH_DBH.md)). Hier
geht es um den ganzen Plot und um die Frage, die der Nutzer im Viewer sofort sieht:
**steht der Marker auf einem Baum?**

## Ergebnis — beide Plots

**plot_07** (Wienerwald, Fichten-Mischbestand, Riegl VZ-400i, ~1410 m²,
**128 Referenzstämme**) — das Ground-Truth-Gegenstück zur Renon-Szene:

| Verfahren | Detektionen | Recall | Precision |
|---|--:|--:|--:|
| `inventory_from_cloud.py` (Baseline) | 59 | 34,4 % | 74,6 % |
| **3DFin (INI der Autoren)** | 121 | **94,5 %** | **100 %** |

3DFin findet 121 von 128 Stämmen und liefert dabei **keinen einzigen Fehlalarm**.
Die Baseline findet ein Drittel. Der Befund ist über beide Plots stabil — er hängt
also nicht an einer Baumart oder an einem Scanner.

## Ergebnis — plot_06 (Wienerwald, Rotbuche, Riegl VZ-2000i, ~1300 m², 68 Referenzstämme)

| Verfahren | Sprache | Detektionen | Recall | Precision |
|---|---|--:|--:|--:|
| `inventory_from_cloud.py` (Baseline) | Python | 97 | 60,3 % | 42,3 % |
| Baseline + Schaftkontrolle | Python | 55 | 57,4 % | **70,9 %** |
| lidR-Eigenbau (`bench_stems_r.R`) | R | 98 | 66,2 % | 45,9 % |
| CspStandSegmentation 0.2.0 | R | 141 | 57,4 % | 27,7 % |
| **3DFin (INI der Autoren)** | Python | 70 | **98,5 %** | **95,7 %** |

**Befund, unbequem und eindeutig: 3DFin ist den übrigen Verfahren auf diesen
Wolken deutlich überlegen** — 67 von 68 Stämmen bei 3 Fehlalarmen. Die eigene
numpy-Baseline und der lidR-Eigenbau produzieren beide mehr Fehlalarme als
Treffer. Das relativiert die Baseline-Zahlen aller bisherigen Szenen und ist der
Grund, 3DFin auf plotweiten TLS-Wolken als Detektor zu setzen statt als
Vergleichsverfahren. Wo die Aussage endet, steht im nächsten Abschnitt —
auf Einzelbäumen und auf dünn abgedeckten Wolken gilt sie **nicht**.

Zu Csp fairerweise: die Ausgabe hat eine Spalte `quality_flag`, die aber nicht
trennt (139 von 141 Detektionen tragen denselben Wert) — ein Filter darüber würde
die Precision nicht retten. Csp ist zudem primär eine **Segmentierung**, nicht ein
Stammdetektor; die niedrige Precision heißt, dass es viele Nicht-Baum-Objekte als
eigene Segmente führt, nicht dass die Segmentierung schlecht wäre.

## Reichweite dieser Aussage — und wo sie endet

Die Zahlen oben gelten für **plotweite TLS-Wolken mit brauchbarer Umfangs­abdeckung**.
Sie übertragen sich nachweislich **nicht** auf die übrigen Wolken der Suite:

| Datensatz | 3DFin | Einordnung |
|---|---|---|
| SegmentedForests plot_06/07 | 95–100 % Precision | Referenzfall |
| **SYSSIFOSS** (Einzelbäume, Feld-GT) | **MAE 7,8 cm** — schlechter als der simple Kreisfit (5,8) und qsm_wood (5,7) | zweckentfremdet: 3DFin ist für Plots gebaut, nicht für isolierte Einzelbäume |
| **Renon** (kein GT) | 37 Detektionen, davon nur **8 mit akzeptiertem BHD**; Überlappung mit unserer Inventur < 50 % | siehe unten |

### Warum 3DFin am Renon-Bestand kaum misst — es liegt nicht an der Konfiguration

Naheliegende Vermutung war das Bodenmodell: 3DFin warnt dort über die
Gelände­modellierung, und `terrain_probe.py` bestätigt einen echten Unterschied —
Renon hat **11,9 cm Geländerauheit** gegen 2,8–3,8 cm auf den Wienerwald-Plots,
bei 35 % Bodenlücken. Ein Durchlauf über `res_cloth` = 0,45 / 0,70 / 1,00 / 1,50
(sonst exakt die Autoren-Parameter) widerlegt das aber: 37–39 Detektionen, 2–4 mit
BHD, Warnung in **allen** Läufen. Das Bodenmodell ist nicht der Engpass.

Der Engpass ist die **Umfangsabdeckung der Stämme**:

| Plot | Bogen Median | Anteil ≥ 202° | Punkte je BH-Scheibe |
|---|--:|--:|--:|
| Renon (4 verschmolzene Standpunkte) | **180°** | **28 %** | **223** |
| plot_06 Buche | 360° | 86 % | 4 604 |
| plot_07 Fichte | 280° | 88 % | 3 263 |

3DFin fordert per Voreinstellung 9 von 16 Sektoren = **202°**. Am Renon-Bestand
erfüllen das nur 28 % der Stämme, auf den Wienerwald-Plots 86–88 %; dazu kommt die
20-fach geringere Punktzahl je Brusthöhen-Scheibe. **3DFins Weigerung ist damit
korrektes Verhalten, kein Versagen** — die Daten tragen dort keinen Durchmesser.

Die unbequeme Kehrseite: unsere eigenen Verfahren liefern an genau diesen Stämmen
trotzdem Zahlen. Sie ruhen dann auf 180°-Bögen. Das ist kein Vorteil unserer
Verfahren, sondern eine Aussage über die Renon-Wolke — vier Standpunkte auf engem
Raum ersetzen keine verteilte Mehrscan-Kampagne.

## Tropischer Regenwald mit Einzelbaum-Wahrheit — Q-ForestLab, Robson Creek

Datensatz: Cherlet et al. (2026), *Benchmarking tree instance segmentation of
terrestrial laser scanning point clouds*, ISPRS J. Photogramm. 231, 230–247
([doi:10.1016/j.isprsjprs.2025.10.033](https://doi.org/10.1016/j.isprsjprs.2025.10.033)),
Daten [Zenodo 16875688](https://doi.org/10.5281/zenodo.16875688), CC BY 4.0
(Q-ForestLab, Universität Gent). Anders als SegmentedForests trägt hier **jeder
Punkt die Baum-ID** (von Hand, neun Bearbeiter, eine Nachkontrolle). Damit fällt die
Grenze „Referenzstämme sind geclustert" (unten) weg, und zum ersten Mal lässt sich
auch die **Einzelbaum-Segmentierung** messen, nicht nur die Detektion.

Ausgewertet: Testgebiet des Plots Robson Creek (TERN-SuperSite, Far North
Queensland), 20 m × 25 m, 30,9 Mio. Punkte (2-cm-Voxel: 20,0 Mio.), 225 Baum-IDs.

**Referenz (52 Bäume):** Stamm in der Testfläche und BHD ≥ 10 cm; ohne messbaren BHD
(Brettwurzel, Schräglage) ab 10 m Höhe. BHD je Referenzbaum aus den eigenen Punkten
des Baumes: robuster Kreisfit in 1,2–1,4 m **plus Schaftkontrolle in 2,0 m**. Ohne
die Kontrolle hätten Unterstand-Bäumchen mit Laub bis zum Boden „Stämme" von
75–145 cm BHD bei 4–6 m Höhe geliefert. 54 Randbäume (Stamm außerhalb oder
angeschnitten) zählen weder als Referenz noch als Fehlalarm.

| Verfahren | Detektionen | Recall | Precision | Lagefehler (Median) |
|---|--:|--:|--:|--:|
| `inventory_from_cloud.py` (Baseline) | 98 | 25,0 % | 52,0 % | 31,8 cm |
| **3DFin** (Autoren-INI plot_06, nur max. Durchmesser 2,5 m / max. Höhe 45 m) | 141 | **86,5 %** | **84,4 %** | 20,4 cm |

**Befund:** Die Rangfolge aus dem Wienerwald hält auch in den Tropen, aber 3DFin
verliert 8–12 Punkte Recall und 11–16 Punkte Precision. Und: **3DFin gibt nur
für 6 von 155 Stämmen einen Durchmesser aus** — im dichten Unterwuchs findet es die
Stämme, akzeptiert aber fast keinen Kreis. Ob das an der INI liegt (Sektoren,
Punktzahl je Schnitt), ist offen.

**Einzelbaum-Segmentierung** (`itcd_cloud.py`, Saat = 3DFin-Stämme): 96,8 % der
Baumpunkte werden zugeordnet, aber nur **25 % der Referenzbäume** erreichen eine
IoU ≥ 0,5 (Mittel 0,40). Im verzahnten Kronendach des Regenwaldes trennt der
Kürzeste-Wege-Ansatz die Kronen nicht — ein klarer, jetzt messbarer Befund.

Szene: `qforest-robsoncreek` (Umschalter Höhe · Ground Truth · Einzelbäume; die
ITCD-Segmente tragen die Farbe ihres besten Referenzbaums). Ergebnisdateien:
`extdata/qforest/robsoncreek_test_*`.

```bash
# nur das Testgebiet aus dem 2,9-GB-ZIP (Range-Request; ZIP ist Deflate64 -> pip install zipfile-deflate64)
python scripts/qforest_bench.py prep robsoncreek_test.ply --out data/qforest/rc_test.npz
python scripts/qforest_bench.py gt   data/qforest/rc_test.npz --out data/qforest/rc_gt.csv
python scripts/qforest_bench.py fin  data/qforest/rc_test.npz extdata/qforest/robsoncreek.ini --out data/qforest/rc_3dfin.csv --work data/qforest/fin
python scripts/inventory_from_cloud.py data/qforest/rc_test.npz data/qforest/rc_base.csv
python scripts/itcd_cloud.py data/qforest/rc_test.npz data/qforest/rc_3dfin.csv --out data/qforest/rc_itcd.npz
python scripts/qforest_bench.py eval data/qforest/rc_test.npz data/qforest/rc_gt.csv \
    --det 3DFin=data/qforest/rc_3dfin.csv --det Baseline=data/qforest/rc_base.csv \
    --itcd data/qforest/rc_itcd.npz --out data/qforest/rc_report.json
python platform/dev/seed_qforest.py qforest-robsoncreek data/qforest/rc_test.npz data/qforest/rc_gt.csv \
    data/qforest/rc_report.json --itcd data/qforest/rc_itcd.npz --lat -17.12 --lon 145.63 \
    --title "Robson Creek (Queensland) — tropischer Regenwald, jeder Baum als Ground Truth (Q-ForestLab)" \
    --plot-info "Testgebiet (20 m x 25 m) des Plots Robson Creek, TERN-SuperSite im tropischen Regenwald von Far North Queensland, Australien."
python platform/dev/publish_scene.py qforest-robsoncreek     # nur diese Szene nach docs/
```

Offen: die drei anderen Plots des Datensatzes (Wytham Woods, Ofental, Litchfield)
mit demselben Ablauf — dann steht derselbe Vergleich über vier Waldtypen.

## Worauf die Fehlalarme sitzen

Weil der Datensatz auch die Nicht-Baum-Klassen labelt, steht hier nicht
„vermutlich Totholz", sondern was es war (Baseline, 56 Fehlalarme):

| Klasse | Anzahl |
|---|--:|
| Strauch / Bodenvegetation | 28 |
| niedrige Vegetation / liegendes Totholz | 10 |
| Äste + Blätter | 10 |
| Nicht-Vegetation, aufrecht in Brusthöhe (Pfahl/Person) | 3 |
| dünner Baum / Zweig | 3 |

## Die Schaftkontrolle ist damit belegt

Der Filter aus `dbh_methods.py` (`stem_continuity`) prüft, ob sich der Stamm über
der Brusthöhe fortsetzt. Er war als Antwort auf Phantom-Marker am Renon-Bestand
entstanden, ohne Beleg. Hier ist er:

| | Precision | Recall | Fehlalarme |
|---|--:|--:|--:|
| ohne | 42,3 % | 60,3 % | 56 |
| mit | **70,9 %** | 57,4 % | **16** |

Er entfernt 40 von 56 Fehlalarmen und kostet 2 echte Bäume. Die übrig bleibenden
Fehlalarme sind überwiegend **Äste** (6) — aufrechte Strukturen, die sich
tatsächlich nach oben fortsetzen; gegen die hilft dieses Kriterium prinzipiell nicht.

## Grenzen

- **Die Klassennamen sind abgeleitet, nicht dokumentiert.** Weder Datensatz noch
  Aufsatz enthalten eine Tabelle Zahl → Name; der Aufsatz sagt nur „Labels 6–9
  correspond to non-vegetation structures". Die Zuordnung stammt aus
  `classes_probe.py` (Höhe über Boden, Clusterzahl und -radius im Brusthöhen-Band,
  vertikale Kontinuität). Klasse 3 = Stamm gilt als sicher: 68 gefundene
  Stammquerschnitte gegen ~69 im Aufsatz genannte Bäume. Nebenklassen sind in
  `data/segforests/classes.json` ausdrücklich als unsicher markiert.
- **Referenzstämme sind geclustert, nicht instanzweise gelabelt.** Der Datensatz
  ist semantisch segmentiert; die Trennung in einzelne Stämme stammt aus dem
  Clustering hier und kann bei sich berührenden Stämmen verschmelzen.
- **n = 1 Plot.** plot_07 (Fichten-Mischbestand) ist geladen, aber noch nicht
  ausgewertet.

## Reproduzieren

```bash
python scripts/zenodo_zip_pick.py "https://zenodo.org/records/17396681/files/SegmentedForests.zip?download=1" --extract "SegmentedForests/pointclouds/plot_06.laz" "SegmentedForests/3DFin_settings/plot_06.ini" --out data/segforests
python scripts/laz_analysis.py data/segforests/plot_06.laz --out data/segforests/plot_06_analysis.npz
python scripts/classes_probe.py data/segforests/plot_06_analysis.npz
python scripts/inventory_from_cloud.py data/segforests/plot_06_analysis.npz data/segforests/plot_06_trees.csv --radius 999 --min-points 60 --arc-min 100
python scripts/run_3dfin_ini.py data/segforests/plot_06_analysis.npz data/segforests/plot_06.ini data/segforests/_3dfin_plot06
python scripts/validate_detection_gt.py data/segforests/plot_06_analysis.npz <detektionen.csv> --classes data/segforests/classes.json
```

R-Teil (die passende Installation ist **`C:\Users\A\R\R-4.4.3`**, nicht die 4.6.1
im PATH — die Pakete sind für 4.4.3 gebaut und ihre DLLs laden in 4.6 nicht):

```bash
"C:/Users/A/R/R-4.4.3/bin/x64/Rscript.exe" scripts/bench_stems_r.R data/segforests/plot_06.laz data/segforests/plot_06_r C:/Users/A/R/lib443
```
