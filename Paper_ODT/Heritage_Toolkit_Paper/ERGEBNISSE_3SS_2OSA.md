# Läufe 3_SS und 2_OSA (03.11.2026)

Ein Pod, RTX A4500 Community (0,19 $/h), 11:59–13:37 UTC, ≈ 0,31 $ (inkl. Fehlstart 11:59–12:04: gerundete
Transformationsmatrix, behoben in 78ec591). gsplat 1.5.3, 30 000 Schritte, halbe Auflösung, Fotos **nicht**
entzerrt (`UNDIST=0`), gelieferte Posen, alle Fotos fürs Training (`TEST_EVERY=1000` → PSNR aus 1 Testbild,
nicht aussagekräftig). PLYs nicht gesichert. Pod gelöscht.

## 3_SS — 473 Fotos, 11 039 781 Referenzpunkte, Transformation s = 0,978

1 241 766 Gaussians, davon 589 814 (Deckkraft ≥ 0,5, in Hülle). Training 12:40–13:10 (inkl. Laden).

| Label | Splats | Median | 95 % | Vollst. 2/5/10 cm |
|---|---|---|---|---|
| alle | 589 814 | 14,2 cm | 2103,4 cm | 0,02 / 0,20 / 0,55 |
| 0 | 19 561 | 5,2 cm | 27,5 cm | 0,02 / 0,20 / 0,64 |
| 1 | 38 766 | 4,2 cm | 14,6 cm | 0,04 / 0,33 / 0,76 |
| 2 | 204 323 | 4,7 cm | 270,8 cm | 0,04 / 0,33 / 0,74 |
| 3 | 217 562 | 1505,9 cm | 2222,4 cm | 0,01 / 0,08 / 0,37 |
| 4 | 9 537 | 9,7 cm | 47,2 cm | 0,02 / 0,18 / 0,59 |
| 5 | 70 004 | 10,7 cm | 65,1 cm | 0,02 / 0,15 / 0,46 |
| 6 | 251 | 18,2 cm | 73,8 cm | 0,01 / 0,08 / 0,36 |
| 7 | 25 173 | 14,2 cm | 62,4 cm | 0,01 / 0,08 / 0,36 |
| 9 | 4 637 | 3,9 cm | 954,7 cm | 0,03 / 0,23 / 0,59 |

(Keine Splats mit Label 8 und 10.) Label 3 (vermutlich Boden): 217 562 Splats mit Median **15 m** — das sind
Gaussians weit über bzw. vor dem Gebäude (Hintergrund, Vegetation, Himmel) innerhalb der Hülle, deren nächster
Referenzpunkt zufällig Boden ist. Der Gesamt-Median 14,2 cm ist dadurch nach oben verzerrt; die Vollständigkeit
ist davon unberührt.

## 2_OSA — 755 Fotos, 7 123 548 Referenzpunkte, Transformation s = 0,605

715 802 Gaussians, davon 371 196 (Deckkraft ≥ 0,5, in Hülle). Training 13:10–13:35.

| Label | Splats | Median | 95 % | Vollst. 2/5/10 cm |
|---|---|---|---|---|
| alle | 371 196 | 13,0 cm | 178,8 cm | 0,03 / 0,25 / 0,72 |
| 0 | 22 103 | 6,3 cm | 35,0 cm | 0,04 / 0,34 / 0,85 |
| 1 | 34 645 | 85,2 cm | 183,5 cm | 0,04 / 0,40 / 0,92 |
| 2 | 19 494 | 9,2 cm | 138,7 cm | 0,03 / 0,30 / 0,85 |
| 3 | 70 860 | 19,7 cm | 212,4 cm | 0,02 / 0,18 / 0,62 |
| 4 | 35 355 | 12,0 cm | 172,7 cm | 0,03 / 0,30 / 0,76 |
| 5 | 121 433 | 10,8 cm | 141,5 cm | 0,03 / 0,26 / 0,71 |
| 7 | 24 824 | 7,6 cm | 40,7 cm | 0,02 / 0,26 / 0,75 |
| 8 | 9 158 | 11,0 cm | 34,8 cm | 0,02 / 0,24 / 0,80 |
| 9 | 33 324 | 38,6 cm | 193,3 cm | 0,04 / 0,30 / 0,74 |

(Keine Splats mit Label 6 und 10.) Label 1 (Säule): Vollständigkeit 0,92, aber Median 85 cm — die Säulen
sind gut abgedeckt, zusätzlich hängen viele Schwebeteilchen in ihrer Nähe.

## Vergleich der drei Gebäude

| Gebäude | Fotos | Ref.-Punkte | Median | Vollst. 5 / 10 cm | beste Klassen (Median) |
|---|---|---|---|---|---|
| 5_CB | 166 | 11,37 Mio. | 12,0 cm | 0,24 / 0,59 | 0, 1, 9: 4–6 cm |
| 3_SS | 473 | 11,04 Mio. | 14,2 cm | 0,20 / 0,55 | 0, 1, 2, 9: 4–5 cm |
| 2_OSA | 755 | 7,12 Mio. | 13,0 cm | 0,25 / 0,72 | 0, 7: 6–8 cm |

Befund über alle drei: Median 12–14 cm, Vollständigkeit bei 10 cm 0,55–0,72; Bögen (0) überall 4–6 cm;
Boden (3) überall am schlechtesten; Schwebeteilchen treiben die 95-%-Werte auf Meter.

## Wiederholung mit Szenen-Sicherung (03.11.2026, 14:47–17:12 UTC)

RTX A4000 (0,17 $/h, ≈ 0,41 $), gleiche Einstellungen, alle drei Gebäude auf einem Pod; Splats diesmal
gesichert (schlanke .ply SH0 in `docs/media/scenes/pellis-*/`, über Workflow `fetch-splats`).

| Gebäude | Median | 95 % | Vollst. 2/5/10 cm | Szene |
|---|---|---|---|---|
| 5_CB | 11,4 cm (vorher 12,0) | 204,7 cm | 0,03 / 0,24 / 0,59 | 415 667 Gaussians, 28 MB |
| 3_SS | 12,8 cm (vorher 14,2) | 2000,7 cm | 0,02 / 0,20 / 0,55 | 600 000 Gaussians, 41 MB |
| 2_OSA | 12,6 cm (vorher 13,0) | 177,8 cm | 0,03 / 0,25 / 0,72 | 486 584 Gaussians, 33 MB |

Vollständigkeit identisch, Median ±1,4 cm → Ergebnisse reproduzierbar (Zufall im Training).
