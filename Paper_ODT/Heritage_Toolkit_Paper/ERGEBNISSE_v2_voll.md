# Lauf v2: volle Auflösung (3872 × 2592), 05.11.2026

Pod: RunPod Community RTX A4500 20 GB (0,19 $/h), gsplat 1.5.3, 30 000 Schritte, FACTOR=1, UNDIST=0,
gelieferte Posen, `test_every` = 1000. Laufzeit inkl. Download: 5_CB 05:29–06:26, 3_SS 06:26–07:44,
2_OSA 07:44–09:03 UTC. Kein Speicherproblem.

## Bildqualität (gsplat-Test, Schritt 7k / 30k)

| Gebäude | PSNR 7k | PSNR 30k | SSIM 30k | LPIPS 30k | Gaussians 30k |
|---|---|---|---|---|---|
| 5_CB | 9.824 | 9.926 | 0.3270 | 0.963 | 458 436 |
| 3_SS | 17.820 | 17.221 | 0.6075 | 0.594 | 1 014 690 |
| 2_OSA | 13.915 | 9.328 | 0.6327 | 0.794 | 621 708 |

Testbild bei `test_every` = 1000 ist jeweils nur Foto 001 (schlecht abgedeckt) → nicht mit Lauf v1 vergleichbar.

Fotostandpunkte (render_views.py, 8 gleichverteilte Trainingsfotos, PSNR dB):
- 5_CB: 9.92, 17.84, 22.06, 21.93, 18.17, 27.38, 22.65, 16.58
- 3_SS: 17.21, 17.26, 21.97, 22.76, 27.74, 23.74, 25.81, 17.05
- 2_OSA: 9.37, 18.86, 16.34, 18.50, 17.83, 16.08, 10.79, 20.48

## Geometrie (Deckkraft ≥ 0,5, in Hülle)

| Gebäude | Splats | Median | 95 % | Vollst. 2/5/10 cm |
|---|---|---|---|---|
| 5_CB | 293 042 | 13.5 cm | 208.6 cm | 0.02 / 0.21 / 0.56 |
| 3_SS | 456 279 | 12.3 cm | 1943.5 cm | 0.02 / 0.18 / 0.52 |
| 2_OSA | 315 514 | 13.7 cm | 177.7 cm | 0.02 / 0.22 / 0.67 |

Pro Klasse siehe `results/geometry_per_class_v2.csv`.
