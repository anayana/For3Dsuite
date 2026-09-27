# Bolderwood — Datenprüfung

Stand: 2026-08-11. Geprüft: alle 10 Dateien in `bolderwood/`, Punktwolken vollständig
gestreamt (kein Subsampling bei den Statistiken).

## Ergebnis

Der Datensatz ist konsistent. Vier Befunde sind für die Weiterverarbeitung relevant,
einer davon ist ein Stolperstein (Punkt 1).

---

## 1. WIDTH/HEIGHT im PCD-Header sind gegenüber der Speicherreihenfolge vertauscht

```
WIDTH 10054   HEIGHT 3771   POINTS 37913634   DATA ascii   FIELDS x y z intensity
```

Nach PCD-Konvention wäre `reshape(HEIGHT, WIDTH)` = `(3771, 10054)`. Das ergibt Müll.

Tatsächlich liegen die Punkte als **10054 aufeinanderfolgende Vertikallinien à 3771 Punkte**
vor. Nachgemessen an den ersten Segmenten von Cloud 19:

| Segment | gültige Punkte | Elevation | Azimut (Median, ρ>1 m) |
|---|---|---|---|
| 0 | 3534 / 3771 | −45,03° … +89,93° | −164,548° |
| 1 | 3552 / 3771 | −45,03° … +89,93° | −164,585° |
| 2 | 3556 / 3771 | −45,03° … +89,90° | −164,620° |
| 3 | 3559 / 3771 | −45,03° … +89,86° | −164,656° |

Innerhalb eines Segments ist der Azimut konstant (IQR 0,037°), die Elevation läuft über
die vollen 134,96° durch. Von Segment zu Segment springt der Azimut um 0,036°.

**Korrekt ist also `reshape(10054, 3771).T`.** Damit ergibt sich ein sauberes
equirektangulares Panorama:

- Winkelauflösung 134,96° / 3770 = **0,0358°/px**, identisch in beiden Achsen
- 10054 × 0,0358° = **359,9°**, also volle 360°-Abdeckung
- Elevationsband −45° bis +90° (Zenit erfasst, Nadir-Kegel fehlt — Stativschatten)

Zur Kontrolle gerendert: `QC_scene19_range_pano.png`, `QC_scene19_intensity_pano.png`
und dasselbe für Szene 45. Bäume stehen senkrecht, Boden unten, Kronendach oben — die
Interpretation stimmt.

Diese vier Bilder liegen **nicht im Repo**: es sind Rauschbilder von je 2–3 MB, die sich
praktisch nicht komprimieren lassen, und der Push dieses Repos scheitert reproduzierbar ab
etwa 1 MB (HTTP 408). Sie werden aus den Rohwolken erzeugt mit

```
python bolderwood/bolderwood_io.py --qc-images
```

Das schreibt sie auf 2514×943 (Kastenmittel, Faktor 4) neben dieses Dokument;
`write_qc_panoramas(scene, reduce=1)` liefert die volle Auflösung 3771×10054. Die
Einfärbung der Reichweite ist eine Regenbogenrampe zwischen dem 1. und 99. Perzentil,
fehlende Returns schwarz — für den Streifentest kommt es nur darauf an, ob das Panorama
durchläuft, nicht auf die exakten Farbwerte.

## 2. Es gibt keine HDRs

Die Stereobilder sind **8 Bit RGB, PACKBITS-komprimiert**, 688×1032×3, `uint8`,
Wertebereich 0–255. Kein Float, kein erweiterter Dynamikumfang.

| | Szene 19 | Szene 45 |
|---|---|---|
| Stereobilder | 32 (16 Paare) | 36 (18 Paare) |
| gesättigte Pixel (=255) | 0,01 – 4,14 %, ⌀ 0,97 % | 0,00 – 6,08 %, ⌀ 1,93 % |

Der Anteil ausgebrannter Pixel ist gering, aber er liegt dort, wo er in einem Wald zu
erwarten ist: im Himmel zwischen den Kronen. Für Beleuchtungsrekonstruktion ist das
zu wenig Dynamik; falls dafür HDRs gebraucht werden, sind sie in diesem Datensatz
nicht enthalten und müssen aus einer anderen Quelle kommen.

## 3. Depth-Maps stammen nachweislich aus genau diesen Punktwolken

Die `.mat`-Dateien enthalten je eine Variable `dMapLiDAR`, 688×1032, `float64`.
Keine Werte ≤ 0.

Der entscheidende Test ist das Maximum:

| | Wolke (exakt, alle Punkte) | Depth-Maps (gepoolt) |
|---|---|---|
| Szene 19 | 125,31 m | 125,31 m |
| Szene 45 | 125,50 m | 125,50 m |

Zentimetergenaue Übereinstimmung in beiden Szenen. Die Depth-Maps sind aus diesen
Wolken gerendert, und zwar als **radiale Distanz**, nicht als z-Tiefe.

Die restliche Verteilung ist erwartungsgemäß nach hinten verschoben, weil die Kameras
nur einen Ausschnitt sehen, während die Wolke das Nahfeld in alle Richtungen
überabtastet:

| Perzentil | 1 | 25 | 50 | 75 | 95 | 99 |
|---|---|---|---|---|---|---|
| S19 Wolke [m] | 1,87 | 5,05 | 9,34 | 13,91 | 27,04 | 43,70 |
| S19 Depth [m] | 3,47 | 7,65 | 12,32 | 21,90 | 40,93 | 62,10 |
| S45 Wolke [m] | 2,17 | 4,39 | 9,83 | 16,57 | 32,35 | 49,36 |
| S45 Depth [m] | 3,49 | 7,93 | 14,04 | 24,50 | 45,33 | 68,66 |

## 4. Die `*_small_*.csv` sind valide Teilmengen

Getestet über Voxel-Belegung gegen die jeweilige Vollwolke:

| Voxelgröße | Szene 19 | Szene 45 |
|---|---|---|
| 2 cm | 96,48 % | 96,28 % |
| 5 cm | 99,45 % | 99,28 % |
| 20 cm | 99,98 % | 99,97 % |

Bei 5 cm liegen über 99 % der Small-Punkte in einem belegten Voxel der Vollwolke. Der
Rest sind Quantisierungseffekte an Voxelgrenzen plus die auf 6 Nachkommastellen
gerundeten CSV-Koordinaten — die Small-Clouds sind minimal versetzt, nicht bitgleich
(erster Punkt S19: CSV `-0.006205 -0.001068 6.590530` vs. PCD `-0.007800 0.000079
6.590712`, Δ ≈ 1,6 mm). `*_small_rgb.csv` ist zeilengleich zu `*_small_xyz.csv`
(710 292 bzw. 619 140 Zeilen), RGB als 0–255.

---

## Zahlen zu den Vollwolken

| | Cloud 19 | Cloud 45 |
|---|---|---|
| Punkte (deklariert = geparst) | 37 913 634 | 37 913 634 |
| davon Nullpunkte (kein Return) | 2 399 071 (6,33 %) | 6 956 680 (18,35 %) |
| gültige Returns | 35 514 563 | 30 956 954 |
| NaN/Inf | 0 | 0 |
| Ausdehnung X × Y × Z [m] | 244,0 × 240,9 × 59,1 | 231,6 × 237,2 × 60,4 |
| Zentroid [m] | −0,22 / 0,23 / 4,13 | −0,22 / −0,28 / 3,57 |
| Median-Distanz | 9,34 m | 9,83 m |
| Intensität | 0,000 – 0,990 | 0,000 – 0,991 |

Beide Wolken sind sensorzentriert (Ursprung = Scannerposition). Fehlende Returns sind
als exakt `(0, 0, 0)` kodiert, **nicht** als NaN — beim Einlesen entsprechend filtern.

Der Unterschied im Nullpunkt-Anteil (6,3 % vs. 18,4 %) ist auffällig, aber plausibel:
Szene 45 hat mehr offenen Himmel. Er deckt sich grob mit dem NaN-Anteil der Depth-Maps
(⌀ 18,0 % bei S19, ⌀ 20,2 % bei S45), wobei die beiden Zahlen nicht direkt vergleichbar
sind, weil die Depth-Maps nur den Kameraausschnitt abdecken.

## Bild-Indizes

Szene 19 hat **16** Aufnahmen: `1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18`
— die Indizes **3 und 13 fehlen**. Sie fehlen aber konsistent in Stereo *und* Depth, es
gibt also keine verwaisten Dateien. Szene 45 ist mit 1–18 vollständig. Links/Rechts
sind in beiden Szenen lückenlos gepaart.

---

## Konsequenzen fürs Einlesen

```python
W, H = 10054, 3771          # Header-WIDTH, Header-HEIGHT
xyzi = parse_pcd_ascii(...)  # (37913634, 4)
pano = xyzi.reshape(W, H, 4).transpose(1, 0, 2)   # -> (3771, 10054, 4), equirect
valid = (pano[..., :3] != 0).any(-1)              # Nullpunkte = kein Return
```

Azimut wächst mit dem Spaltenindex, Elevation fällt mit dem Zeilenindex (in den
QC-PNGs wurde die Elevationsachse gespiegelt, damit oben oben ist).

Die Dateien sind ASCII-PCD, 1,43 GB je Wolke entpackt. Ein Streaming-Parser
(`np.fromstring(chunk, dtype=np.float32, sep=' ')` über 16-MB-Blöcke direkt aus dem ZIP)
schafft eine Wolke in ~40 s ohne Entpacken auf Platte — die Skripte dazu liegen als
`scan_pcd.py` und `check_small.py` im Ausgabeordner.
