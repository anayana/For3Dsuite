# Manuskript Paper B — Entwurf (Stand 03.11.2026)

Zieljournal: *Journal of Cultural Heritage* (Elsevier, hybrid, Abo-Weg ohne Gebühr); Ausweich: *PFG*.
Sprache: Englisch. Platzhalter `[TODO …]` = fehlt noch (Demo, Abbildungen).
Alle Zahlen aus `ERGEBNISSE_5CB.md` und `ERGEBNISSE_3SS_2OSA.md`; nichts geschätzt.

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
class, for three buildings (166–755 images, 7–11 million reference points). The median distance of
splat centres to the reference is 12.0–14.2 cm, and 55–72 % of the reference points have a splat within
10 cm. Arches reach 4–6 cm in all three buildings, while floors are consistently the worst class and
floating Gaussians push the 95th percentile to metres. Hold-out image quality is limited (PSNR 14–16 dB) because the photogrammetric capture covers
novel viewpoints poorly — a property of survey-oriented image sets rather than of the pipeline. We report
two practical pitfalls (re-undistorting already undistorted images; trusting hold-out PSNR on survey data)
and release the full pipeline and an offline browser tool for annotated splat walkthroughs as FOSS.

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

**Image-based heritage recording.** Photogrammetry and terrestrial laser scanning are the established
techniques for metric heritage documentation, delivering dense point clouds and meshes with known
accuracy (Remondino, 2011). Structure-from-Motion pipelines such as COLMAP (Schönberger and Frahm, 2016)
have made the image-based route accessible, and the resulting point clouds are increasingly annotated
with architectural classes for semantic analysis (Matrone et al., 2020). The dataset used here follows
this line: images from photogrammetric surveys together with georeferenced, manually labelled point
clouds of five historic buildings (Pellis et al., 2021, 2025).

**Radiance fields.** Neural Radiance Fields (NeRF) represent a scene as a continuous volumetric function
optimised from posed images (Mildenhall et al., 2020), and extensions handle unbounded scenes
(Barron et al., 2022) and photometric variation between images (Martin-Brualla et al., 2021). For
heritage, critical assessments have shown that NeRF geometry lags behind photogrammetry in accuracy and
completeness (Remondino et al., 2023).

**3D Gaussian Splatting.** 3DGS replaces the implicit field with millions of explicit anisotropic
Gaussians that are rasterised in real time (Kerbl et al., 2023). Open implementations such as gsplat
(Ye et al., 2025) make the method usable outside research labs. Because the standard objective optimises
only image appearance, Gaussian centres are not constrained to lie on surfaces; variants regularise the
geometry by aligning Gaussians with surfaces (Guédon and Lepetit, 2024) or collapsing them to 2D discs
(Huang et al., 2024). Evaluations nevertheless report mostly image metrics — PSNR, SSIM (Wang et al.,
2004) and LPIPS (Zhang et al., 2018) — on held-out views, which says little about the metric quality a
heritage practitioner needs.

**Gap.** We are not aware of an evaluation that compares standard 3DGS against a labelled photogrammetric
reference *per architectural class* on openly licensed data, with a fully reproducible pipeline. This
paper provides such a baseline and documents how survey-oriented image sets behave when used for 3DGS.

## 3. Data and methods

### 3.1 Dataset

Pellis, Masiero, Betti, Tucci, Grussenmeyer (2025), *Data in Brief* 60, doi:10.1016/j.dib.2025.111661;
Zenodo 14626611, CC BY 4.0. Five historic buildings, images from photogrammetric surveys, georeferenced
point clouds, manually labelled with ten ArCH classes. Per building: RGB images, interior orientation
(K, k1–k3, p1–p2), exterior orientation per image (centre, ω φ κ, R), a similarity transform (s, R, t) from
the camera frame to the point-cloud frame, and the labelled point cloud (X Y Z R G B label Nx Ny Nz).

Three of the five buildings are used:

| Building | Images | Reference points | Transform scale s |
|---|---|---|---|
| 5_CB | 166 | 11 372 937 | 1.3441 |
| 3_SS | 473 | 11 039 781 | 0.978 |
| 2_OSA | 755 | 7 123 548 | 0.605 |

5_CB images: 3872 × 2592 px, f = 3054.46 px. The transforms of 3_SS and 2_OSA are stored with rounded
coefficients (orthogonality deviation ≈ 1e-3); the rotation part is re-orthonormalised by SVD.

Classes (Pellis et al., 2025, following ArCH): 0 arch, 1 column, 2 moulding, 3 floor, 4 door/window,
5 wall, 6 stair, 7 vault, 8 roof, 9 other; 10 background (introduced for the images; in the point cloud of
5_CB it marks points not assigned to a building element). The reference cloud was produced
photogrammetrically (Agisoft Metashape), scaled and placed in a local metric system by alignment with a TLS
point cloud (manual pre-alignment + ICP), cleaned and subsampled to a minimum point spacing of 0.01 m
(Pellis et al., 2025). It is therefore a photogrammetric reference in TLS scale, not an independent TLS survey.

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
| 10 background | 27 893 | 59.7 cm | 483.5 cm | 0.00 / 0.01 / 0.03 |


Befund: Gut beobachtete, kontrastreiche Bauteile 4–7 cm; Boden und Dach schlechter (flache Blickwinkel,
wenig Textur bzw. kaum Sicht von unten); 95-%-Werte > 1 m = Schwebeteilchen (floaters).

Figures: Fig. 1 `figures/fig1_completeness_10cm.png` (completeness at 10 cm per class and building),
Fig. 2 `figures/fig2_median.png` (median distance, log scale; * = floater-dominated).

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

### 4.3 Buildings 3_SS and 2_OSA

Same settings as 5_CB (all images, 30 000 iterations, images not re-undistorted).

| Building | Splats kept | Median | 95 % | Compl. 2 / 5 / 10 cm |
|---|---|---|---|---|
| 5_CB | 340 994 | 12.0 cm | 254.3 cm | 0.03 / 0.24 / 0.59 |
| 3_SS | 589 814 | 14.2 cm | 2103.4 cm | 0.02 / 0.20 / 0.55 |
| 2_OSA | 371 196 | 13.0 cm | 178.8 cm | 0.03 / 0.25 / 0.72 |

Per class (median / completeness at 10 cm):

| Class | 5_CB | 3_SS | 2_OSA |
|---|---|---|---|
| 0 arch | 4.4 cm / 0.92 | 5.2 cm / 0.64 | 6.3 cm / 0.85 |
| 1 column | 5.7 cm / 0.98 | 4.2 cm / 0.76 | 85.2 cm / 0.92 |
| 2 moulding | 6.6 cm / 0.75 | 4.7 cm / 0.74 | 9.2 cm / 0.85 |
| 3 floor | 25.6 cm / 0.33 | 1505.9 cm / 0.37 | 19.7 cm / 0.62 |
| 4 door/window | 10.2 cm / 0.81 | 9.7 cm / 0.59 | 12.0 cm / 0.76 |
| 5 wall | 8.4 cm / 0.75 | 10.7 cm / 0.46 | 10.8 cm / 0.71 |
| 6 stair | 10.3 cm / 0.45 | 18.2 cm / 0.36 | — |
| 7 vault | 11.4 cm / 0.74 | 14.2 cm / 0.36 | 7.6 cm / 0.75 |
| 8 roof | 13.3 cm / 0.59 | — | 11.0 cm / 0.80 |
| 9 other | 4.7 cm / 0.86 | 3.9 cm / 0.59 | 38.6 cm / 0.74 |

(— = class not present among the kept splats.) Two medians are dominated by floaters rather than surface
error: in 3_SS, 217 562 Gaussians in front of or above the building (background, vegetation, sky) fall
inside the hull and have a floor point as nearest neighbour (median 15 m); in 2_OSA the columns are well
covered (0.92) but surrounded by floaters (median 85 cm). Completeness is unaffected by floaters and is
therefore the more robust indicator; accuracy needs floater removal before it describes the surface.

## 5. Browser tool [TODO — braucht eine gesicherte .ply; sonst Abschnitt streichen]

Splat + Medien-Marker im Browser-Studio (`create.html`), Export als eine offline lauffähige HTML-Datei
(`export_static.py --html-only`). Abbildung + Bedienablauf.

## 6. Discussion

- Für Denkmalpflege: 3DGS liefert **Darstellung**, keine **Messung** — Zentimeter-Genauigkeit nur an gut
  beobachteten Bauteilen; Referenzvermessung bleibt nötig.
- Klassenabhängigkeit erklärt durch Sichtbarkeit/Textur (Boden, Dach).
- Grenzen: drei Gebäude eines Datensatzes; Median ohne Floater-Filter; Splat-Zentren statt gerenderter Tiefe; Standard-Trainer ohne
  Geometrie-Regularisierung (2DGS/SuGaR wären Vergleich).

## 7. Conclusion

Standard 3D Gaussian Splatting, trained on the published orientations of a photogrammetric survey,
places its Gaussians within a few centimetres of the reference surface on well-observed architectural
elements, but not on floors, roofs and sparsely seen parts, and it adds floaters that a measurement
workflow must remove. For building 5_CB the median deviation is 12.0 cm with 59 % completeness at
10 cm, and the two further buildings confirm the picture (median 13.0–14.2 cm, completeness at 10 cm
0.55–0.72): arches stay at 4–6 cm in all three, floors are the weakest class throughout. 3DGS is therefore a strong medium
for presenting and sharing heritage — walkthroughs, annotation, dissemination — while metric statements
should still rest on the photogrammetric or laser-scanning survey. Two practical lessons transfer to other
projects: check whether published images are already undistorted before applying distortion models, and
do not read held-out PSNR on survey imagery as reconstruction quality. Future work should test
geometry-regularised variants (2DGS, SuGaR) on the same benchmark and evaluate rendered depth instead of
Gaussian centres. All code is released as free software, and the data are openly licensed, so the
comparison can be repeated and extended at no cost.


## Data and code availability

Data: Pellis et al. (2025), Zenodo 14626611 (CC BY 4.0). Code, unit tests and all result tables:
Zenodo, doi:[DOI nach Freigabe des Zenodo-Release] (GPL-3.0-or-later; tables CC BY 4.0).

## References

(DOIs vor Einreichung prüfen — doi.org war in der Arbeitssitzung gesperrt.)

- Barron, J.T., Mildenhall, B., Verbin, D., Srinivasan, P.P., Hedman, P., 2022. Mip-NeRF 360: Unbounded
  anti-aliased neural radiance fields. In: Proc. IEEE/CVF CVPR, pp. 5470–5479.
- Guédon, A., Lepetit, V., 2024. SuGaR: Surface-aligned Gaussian splatting for efficient 3D mesh
  reconstruction and high-quality mesh rendering. In: Proc. IEEE/CVF CVPR, pp. 5354–5363.
- Huang, B., Yu, Z., Chen, A., Geiger, A., Gao, S., 2024. 2D Gaussian splatting for geometrically accurate
  radiance fields. In: ACM SIGGRAPH 2024 Conference Papers. doi:10.1145/3641519.3657428.
- Kerbl, B., Kopanas, G., Leimkühler, T., Drettakis, G., 2023. 3D Gaussian splatting for real-time radiance
  field rendering. ACM Trans. Graph. 42 (4), 139. doi:10.1145/3592433.
- Martin-Brualla, R., Radwan, N., Sajjadi, M.S.M., Barron, J.T., Dosovitskiy, A., Duckworth, D., 2021. NeRF
  in the wild: Neural radiance fields for unconstrained photo collections. In: Proc. IEEE/CVF CVPR,
  pp. 7210–7219.
- Matrone, F., Lingua, A., Pierdicca, R., Malinverni, E.S., Paolanti, M., Grilli, E., Remondino, F.,
  Murtiyoso, A., Landes, T., 2020. A benchmark for large-scale heritage point cloud semantic segmentation.
  Int. Arch. Photogramm. Remote Sens. Spatial Inf. Sci. XLIII-B2-2020, 1419–1426.
- Mildenhall, B., Srinivasan, P.P., Tancik, M., Barron, J.T., Ramamoorthi, R., Ng, R., 2020. NeRF:
  Representing scenes as neural radiance fields for view synthesis. In: Proc. ECCV, pp. 405–421.
- Pellis, E., Masiero, A., Tucci, G., Betti, M., Grussenmeyer, P., 2021. Assembling an image and point
  cloud dataset for heritage buildings semantic segmentation. Int. Arch. Photogramm. Remote Sens. Spatial
  Inf. Sci. XLVI-M-1-2021, 539–546. doi:10.5194/isprs-archives-XLVI-M-1-2021-539-2021.
- Pellis, E., Masiero, A., Betti, M., Tucci, G., Grussenmeyer, P., 2025. A photogrammetric image-point
  dataset for the semantic segmentation of heritage buildings. Data in Brief 60, 111661.
  doi:10.1016/j.dib.2025.111661. Data: Zenodo 14626611 (CC BY 4.0).
- Remondino, F., 2011. Heritage recording and 3D modeling with photogrammetry and 3D scanning. Remote
  Sensing 3 (6), 1104–1138. doi:10.3390/rs3061104.
- Remondino, F., Karami, A., Yan, Z., Mazzacca, G., Rigon, S., Qin, R., 2023. A critical analysis of
  NeRF-based 3D reconstruction. Remote Sensing 15 (14), 3585. doi:10.3390/rs15143585.
- Schönberger, J.L., Frahm, J.-M., 2016. Structure-from-motion revisited. In: Proc. IEEE CVPR,
  pp. 4104–4113.
- Umeyama, S., 1991. Least-squares estimation of transformation parameters between two point patterns.
  IEEE Trans. Pattern Anal. Mach. Intell. 13 (4), 376–380.
- Virtanen, P., et al., 2020. SciPy 1.0: Fundamental algorithms for scientific computing in Python.
  Nature Methods 17, 261–272.
- Wang, Z., Bovik, A.C., Sheikh, H.R., Simoncelli, E.P., 2004. Image quality assessment: From error
  visibility to structural similarity. IEEE Trans. Image Process. 13 (4), 600–612.
- Ye, V., Li, R., Kerr, J., Turkulainen, M., Yi, B., Pan, Z., Seiskari, O., Ye, J., Hu, J., Tancik, M.,
  Kanazawa, A., 2025. gsplat: An open-source library for Gaussian splatting. J. Mach. Learn. Res. 26 (34),
  1–17.
- Zhang, R., Isola, P., Efros, A.A., Shechtman, E., Wang, O., 2018. The unreasonable effectiveness of deep
  features as a perceptual metric. In: Proc. IEEE CVPR, pp. 586–595.

## Costs

Alle GPU-Läufe auf RunPod (Community, 0,17–0,23 $/h); 5_CB-Endlauf ≈ 0,12 $; 3_SS + 2_OSA ≈ 0,31 $.
