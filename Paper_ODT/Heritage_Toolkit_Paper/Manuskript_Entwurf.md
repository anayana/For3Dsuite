# Manuskript Paper B — Entwurf (Stand 02.11.2026)

Zieljournal: *Journal of Cultural Heritage* (Elsevier, hybrid, Abo-Weg ohne Gebühr); Ausweich: *PFG*.
Sprache: Englisch. Platzhalter `[TODO …]` = fehlt noch (3_SS-Lauf, Demo, Abbildungen).
Alle Zahlen aus `ERGEBNISSE_5CB.md`; nichts geschätzt.

---

## Title (Arbeitstitel)

How close is a Gaussian splat to the survey? Geometric accuracy of 3D Gaussian Splatting against
photogrammetric reference point clouds of historic buildings, and an open browser tool for annotated walkthroughs

## Abstract (Entwurf, ~200 Wörter)

3D Gaussian Splatting (3DGS) produces photorealistic, real-time walkthroughs from ordinary photographs
and is increasingly proposed for heritage documentation. Its geometric reliability, however, is rarely
measured against an independent survey. We train 3DGS (gsplat 1.5.3, 30 000 iterations) on the open
Pellis et al. (2025) heritage dataset, using the published camera orientations, and compare the splat
centres with the labelled photogrammetric reference point cloud (11.4 million points) per architectural
class. For building 5_CB the median distance of splat centres to the reference is 12.0 cm; 59 % of the
reference points have a splat within 10 cm. Arches and columns reach 4–6 cm with 92–98 % completeness at 10 cm, while floors, roofs and one
undocumented class remain at 13–60 cm. Hold-out image quality is limited (PSNR 14–16 dB) because the photogrammetric capture covers
novel viewpoints poorly — a property of survey-oriented image sets rather than of the pipeline. We report
two practical pitfalls (re-undistorting already undistorted images; trusting hold-out PSNR on survey data)
and release the full pipeline and an offline browser tool for annotated splat walkthroughs as FOSS.
[TODO: 3_SS-Zahlen ergänzen]

**Keywords:** 3D Gaussian Splatting; heritage documentation; photogrammetry; point cloud comparison;
accuracy assessment; open-source software

## 1. Introduction

- 3DGS (Kerbl et al. 2023) als schnelle, fotorealistische Darstellung; Kulturerbe-Anwendungen nehmen zu.
- Lücke: Bildqualität (PSNR/SSIM/LPIPS) wird berichtet, **Geometrie gegen eine unabhängige Vermessung
  kaum** — für Denkmalpflege entscheidend (Maße, Verformungen, Bauteile).
- Beitrag:
  1. Reproduzierbarer Vergleich 3DGS ↔ photogrammetrische Referenz **je Bauteilklasse** auf offenen Daten
     (CC BY 4.0).
  2. Zwei dokumentierte Fallstricke mit Diagnoseweg (Abschnitt 4.2).
  3. Offenes Werkzeug: Splat + Medien-Marker als eine offline lauffähige HTML-Datei. [TODO Demo]

## 2. Related work

[TODO: Literatur — 3DGS (Kerbl 2023), gsplat (Ye et al. 2024), 3DGS-Geometrie (SuGaR, 2DGS),
Heritage-3DGS-Studien, ArCH-Klassen (Matrone et al. 2020), Pellis et al. 2021/2022/2025.]

## 3. Data and methods

### 3.1 Dataset

Pellis, Masiero, Betti, Tucci, Grussenmeyer (2025), *Data in Brief* 60, doi:10.1016/j.dib.2025.111661;
Zenodo 14626611, CC BY 4.0. Five historic buildings, images from photogrammetric surveys, georeferenced
point clouds, manually labelled with ten ArCH classes. Per building: RGB images, interior orientation
(K, k1–k3, p1–p2), exterior orientation per image (centre, ω φ κ, R), a similarity transform (s, R, t) from
the camera frame to the point-cloud frame, and the labelled point cloud (X Y Z R G B label Nx Ny Nz).

Building **5_CB**: 166 images, 3872 × 2592 px, f = 3054.46 px; 11 372 937 reference points; transform
scale s = 1.3441. [TODO 3_SS]

Labels (ArCH order, confirmed for 0 = arch, 1 = column; 2–9 in list order, **10 not documented —
check article**): 0 arch, 1 column, 2 moulding, 3 floor, 4 door/window, 5 wall, 6 stair, 7 vault,
8 roof, 9 other, 10 [TODO].

### 3.2 Camera model

Published poses converted to COLMAP (photogrammetric −Z → OpenCV +Z), transformed into the point-cloud
frame (C' = sR_tC + t, R' = RR_tᵀ). **Images are used as published, without further undistortion**:
an independent COLMAP reconstruction with per-image focal length and k1 (SIMPLE_RADIAL, 90 images
registered) yields median f = 1526.9 px at half resolution (published 1527.2 px), median k1 = 0.0000,
and camera centres within 2.3 cm (median; 95 %: 7.1 cm) and 0.12° of the published poses. The released
images are therefore already undistorted and the published orientation is consistent with them.

### 3.3 3DGS training

gsplat 1.5.3 `simple_trainer` (default strategy), 30 000 iterations, half resolution (1936 × 1296),
initialised with 300 000 points sampled from the reference cloud, all 166 images for training
(`test_every` = 1000). Hardware: one RunPod GPU (Tesla V100 16 GB), ≈ 20 min training.
Normalisation of the trainer is inverted on export, so splats are in the reference frame.

### 3.4 Geometric comparison

Splat centres with opacity ≥ 0.5 inside the reference bounding hull (+ margin). Accuracy: distance splat
→ nearest reference point (median, 95th percentile). Completeness: share of reference points with a splat
within 2 / 5 / 10 cm. Per label via the reference point of each splat (KD-tree, SciPy).
Script: `scripts/eval_splat_geometry.py`.

### 3.5 Image quality (diagnostic)

Separate runs with every 8th image held out: PSNR, SSIM, LPIPS (gsplat), plus exposure-compensated PSNR
(per-channel gain/offset fitted render → photo) in `scripts/splat_diag.py`.

## 4. Results

### 4.1 Geometry, building 5_CB

340 994 splats (of 541 477) pass the filter.

| Class | Splats | Median | 95 % | Compl. 2 / 5 / 10 cm |
|---|---|---|---|---|
| all | 340 994 | 12.0 cm | 254.3 cm | 0.03 / 0.24 / 0.59 |
| 0 arch | 8 902 | 4.4 cm | 49.7 cm | 0.08 / 0.52 / 0.92 |
| 1 column | 34 388 | 5.7 cm | 111.5 cm | 0.11 / 0.66 / 0.98 |
| 2 moulding | 8 030 | 6.6 cm | 39.9 cm | 0.03 / 0.31 / 0.75 |
| 3 floor | 30 557 | 25.6 cm | 86.5 cm | 0.01 / 0.09 / 0.33 |
| 4 door/window | 6 408 | 10.2 cm | 46.3 cm | 0.03 / 0.32 / 0.81 |
| 5 wall | 81 730 | 8.4 cm | 54.3 cm | 0.03 / 0.31 / 0.75 |
| 6 stair | 26 995 | 10.3 cm | 118.2 cm | 0.01 / 0.12 / 0.45 |
| 7 vault | 27 152 | 11.4 cm | 39.9 cm | 0.03 / 0.29 / 0.74 |
| 8 roof | 81 154 | 13.3 cm | 472.8 cm | 0.02 / 0.19 / 0.59 |
| 9 other | 7 785 | 4.7 cm | 99.5 cm | 0.08 / 0.48 / 0.86 |
| 10 [TODO] | 27 893 | 59.7 cm | 483.5 cm | 0.00 / 0.01 / 0.03 |

(Klassennamen 2–10 noch gegen den Artikel prüfen.)

Befund: Gut beobachtete, kontrastreiche Bauteile 4–7 cm; Boden und Dach schlechter (flache Blickwinkel,
wenig Textur bzw. kaum Sicht von unten); 95-%-Werte > 1 m = Schwebeteilchen (floaters).

### 4.2 Pitfalls

1. **Double undistortion.** Applying the published distortion coefficients to the already undistorted
   images distorted them: geometry median 14.9 cm (vs. 12.0 cm), and COLMAP with one shared pinhole
   camera found a focal length 6 % too short and registered only 97 / 166 images.
2. **Hold-out PSNR on survey imagery.** With correct inputs, training loss reaches 0.038 but held-out
   PSNR stays at 14.4 dB (16.2 dB exposure-compensated; per image 12.1–21.8 dB). Renders of held-out views
   are sharp on well-covered parts (vault, columns) and break down on ground and vegetation seen from few
   directions. Hold-out PSNR therefore measures capture coverage, not reconstruction fidelity.

Diagnostic chain (Tabelle im Anhang): orientation flag, initial cloud, axis convention, published poses,
undistortion, focal length per image, exposure — each tested in a separate run (`ERGEBNISSE_5CB.md`).

### 4.3 Second building [TODO 3_SS]

## 5. Browser tool [TODO]

Splat + Medien-Marker im Browser-Studio (`create.html`), Export als eine offline lauffähige HTML-Datei
(`export_static.py --html-only`). Abbildung + Bedienablauf.

## 6. Discussion

- Für Denkmalpflege: 3DGS liefert **Darstellung**, keine **Messung** — Zentimeter-Genauigkeit nur an gut
  beobachteten Bauteilen; Referenzvermessung bleibt nötig.
- Klassenabhängigkeit erklärt durch Sichtbarkeit/Textur (Boden, Dach).
- Grenzen: ein (zwei) Gebäude; Splat-Zentren statt gerenderter Tiefe; Standard-Trainer ohne
  Geometrie-Regularisierung (2DGS/SuGaR wären Vergleich).

## 7. Conclusion [TODO]

## Data and code availability

Daten: Zenodo 14626611 (CC BY 4.0). Code: `scripts/pellis_to_colmap.py`, `train_pellis_runpod.sh`,
`eval_splat_geometry.py`, `colmap_align.py`, `splat_diag.py` (FOSS). [TODO Zenodo-Release des Codes]

## Costs

Alle GPU-Läufe auf RunPod (Community, 0,17–0,23 $/h); 5_CB-Endlauf ≈ 0,12 $.
