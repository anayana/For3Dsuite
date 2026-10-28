# Erster 3DGS-Lauf: Gebäude 5_CB (28.10.2026)

Pod: RunPod Community RTX A4500 (0,19 $/h), gsplat 1.5.3, 30 000 Schritte, halbe Auflösung (1936×1296),
Initwolke 300 000 Punkte aus `1_point_cloud.txt`. Training 15:21 min. Pod danach gelöscht, kein
Volume übrig. Die PLY (107 MB) wurde **nicht** gesichert (Lauf gilt als Fehlversuch, s. u.).

## Bildqualität (gsplat, Testbilder jedes 8. Foto)

| Schritt | PSNR | SSIM | LPIPS | Gaussians |
|---|---|---|---|---|
| 7 000 | 13,63 | 0,549 | 0,807 | 357 310 |
| 30 000 | 13,39 | 0,521 | 0,710 | 448 304 |

PSNR ~13 dB ist für 3DGS sehr schlecht (übliche Werte 20–30 dB) und steigt nicht mit dem Training →
**die Kameraposen passen nicht sauber zu den Fotos**.

## Geometrie (Splat-Zentren, Deckkraft ≥ 0,5, gegen 11,37 Mio. Referenzpunkte)

| Label | Splats | Median | 95 % | Vollst. 2/5/10 cm |
|---|---|---|---|---|
| alle | 299 108 | 14,9 cm | 223,8 cm | 0,02 / 0,20 / 0,58 |
| 0 | 6 309 | 7,7 cm | 64,3 cm | 0,04 / 0,34 / 0,82 |
| 1 | 29 855 | 13,1 cm | 113,5 cm | 0,08 / 0,55 / 0,96 |
| 2 | 6 011 | 9,2 cm | 44,6 cm | 0,02 / 0,23 / 0,72 |
| 3 | 28 732 | 24,8 cm | 84,8 cm | 0,01 / 0,08 / 0,32 |
| 4 | 5 328 | 12,4 cm | 50,1 cm | 0,02 / 0,22 / 0,72 |
| 5 | 70 012 | 11,1 cm | 65,1 cm | 0,03 / 0,26 / 0,73 |
| 6 | 26 578 | 12,6 cm | 116,5 cm | 0,01 / 0,12 / 0,45 |
| 7 | 26 787 | 12,2 cm | 39,7 cm | 0,02 / 0,24 / 0,73 |
| 8 | 67 337 | 14,8 cm | 456,6 cm | 0,01 / 0,17 / 0,60 |
| 9 | 5 631 | 12,4 cm | 306,7 cm | 0,03 / 0,29 / 0,72 |
| 10 | 26 528 | 57,8 cm | 508,1 cm | 0,00 / 0,01 / 0,04 |

Die Zahlen sind wegen der schlechten Posen **nicht** paperfähig. Bedeutung der Label-Nummern noch
offen (Data-in-Brief-Artikel).

## Verdacht und nächster Schritt

Posenprobe (Tiefenpuffer): Standard-Konvention 0,16 vs. Gegenprobe 0,05 — schwach. Fotos mit
`Orientation = 1` (89 von 166, z. B. 040–049, 054–056, 063–139) haben KAPPA ≈ ±90°. Verdacht: diese
Bilddateien sind gegenüber den Posen um 90° gedreht gespeichert (oder umgekehrt). Prüfung ohne GPU:
SIFT-Relativpose an zwei Fotos mit `Orientation = 1` (wie bei 001/002), einmal wie gespeichert,
einmal um ±90° gedreht. Kosten 0 $.
