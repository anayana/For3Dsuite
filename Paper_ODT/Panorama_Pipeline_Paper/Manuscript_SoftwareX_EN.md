% An open, containerized pipeline turning multi-image captures — from consumer 360° cameras to terrestrial laser scanners — into web-navigable 3D scenes
%
%

**Authors:** [To be completed]
**Corresponding author:** [name, affiliation, e-mail]
**Target journal:** SoftwareX (Elsevier) — Original Software Publication

---

## Abstract

Walkable 360° panoramas and point clouds are valuable for documentation,
monitoring, and outreach, yet their production is usually tied to proprietary,
cloud-bound toolchains. We present a fully open-source, containerized processing
chain with a graphical user interface that turns multi-image captures into
walkable, web-based 3D scenes. The chain unifies two input classes that are
normally handled separately: (i) captures without known pose (consumer and DSLR
fisheye), assembled by stitching (Hugin), and (ii) the RGB images of terrestrial
laser scanners, whose poses are stored in the E57 file and can therefore be
reprojected directly — a seldom-used by-product. Output is served by an
open-source web viewer (Pannellum, three.js), self-hostable through Caddy and
Garage, fully packaged in Docker. In an evaluation against eleven CC0 reference
panoramas, the pose-based branch outperforms stitching on every measure (26.9 vs
23.0 dB PSNR, 0.886 vs 0.837 SSIM, 0.10 vs 0.14 px seam offset), reconstructs all
eleven scenes versus six, and does so roughly seven times faster. Both branches
run fully automatically without manual control points. The software, container
recipe, and evaluation code are openly available; example data are CC-BY-4.0 and
CC0.

**Keywords:** panorama stitching; 360° imaging; terrestrial laser scanning; E57;
open-source; self-hosting; Docker; web visualization; photogrammetry

---

## Code metadata

| | |
|---|---|
| Current code version | v1.0 |
| Permanent link to code/repository | https://github.com/anayana/For3Dsuite |
| Permanent link to reproducible capsule | [Zenodo DOI to be minted on submission] |
| Legal code license | [OSI license — to be finalized] |
| Code versioning system | git |
| Languages / tools | Python, JavaScript; Hugin, GIMP, Pannellum, three.js, Caddy, Garage, Docker |
| Compilation / runtime | Docker + Compose (single command) |
| Support e-mail | [contact] |

---

## 1. Motivation and significance

Interactive 360° panoramas and 3D point clouds are increasingly used to document
and communicate spatial states — in forest and environmental monitoring,
surveying, cultural heritage, and teaching. Two obstacles recur in practice.
First, the common routes are either proprietary and cloud-bound (camera apps with
vendor hosting) or fragmented: a stitching tool, a web viewer, and a server must
be wired together by hand, with no reproducible, containerized path from raw
frames to a published, walkable scene. Second, a valuable data source is routinely
discarded: terrestrial laser scanners (TLS) acquire RGB images whose camera poses
are stored alongside the geometry in the E57 exchange format, yet these images are
usually treated only as a means to colourize the point cloud, not as navigable
panoramas in their own right.

We address both with a single open-source tool. Its contribution is not any
individual component — Hugin, Pannellum, and GIMP are established — but their
**integration into one automated, containerized, GUI-driven, vendor-agnostic
chain**, and specifically the **unification of the two input classes**: captures
whose pose must be estimated (consumer/DSLR fisheye) and captures whose pose is
already known (scanner RGB in E57). The former are stitched; the latter are
reprojected directly to the equirectangular domain, which is faster and free of
stitching failure modes. The same output can be enriched with data derived from
the point cloud (stem detection, diameter at breast height, height, crown
metrics, quantitative structure models, growth projection) and served fully
self-hosted, giving data sovereignty without a cloud dependency.

The tool spans the cost and device spectrum — from a ~20 € consumer 360° camera to
a six-figure TLS — into the same web scene, lowering the barrier for reproducible
spatial documentation.

## 2. Software description

### 2.1 Software architecture

The system is packaged as a set of Docker services orchestrated by Compose: a
processing/API service (Python, FastAPI job queue), an S3-compatible object store
(Garage), a reverse proxy with automatic TLS (Caddy), and a browser-based studio
GUI. A single command brings up a reproducible stack.

At ingestion the tool determines the input class automatically
(`detect_input_class`): an uploaded `.e57` triggers **reprojection**; a single
image with a 2:1 aspect ratio is accepted as a finished equirectangular panorama;
several images trigger **stitching**. A single non-2:1 image is deliberately
rejected rather than guessed, so the tool never silently mis-handles ambiguous
input. In the container, the same upload endpoint without a declared type
correctly recognizes `equirect` (one 2:1 image) and `fisheye` (six frames) and
runs the corresponding chain through to a published scene.

### 2.2 Software functionalities

- **Stitching branch** (pose unknown): Hugin/Panotools with automatic control-point
  detection (`cpfind`, `cpclean`), optimization (`autooptimiser`), and seam
  blending (`nona`, `enblend`); no manual control points.
- **Reprojection branch** (pose known): the per-image poses from the E57 are used
  to resample the RGB images into a seamless equirectangular panorama (bilinear
  sampling).
- **Pre-processing**: batch exposure/crop/nadir–zenith handling (GIMP Script-Fu).
- **Viewing**: web-based panorama and point-cloud viewer (Pannellum, three.js),
  multi-resolution output.
- **Enrichment**: georeferenced markers carrying point-cloud-derived inventory
  data overlaid on the walkable scene.
- **Publishing**: self-hosted (Caddy + Garage) or as a static export.

## 3. Illustrative examples

**Scanner RGB → walkable scene with data (Renon / ICOS IT-Ren).** A TLS E57 with
six pinhole images and poses per setup is reprojected to a seamless equirectangular
panorama; the co-registered point cloud is added, and inventory markers (stem
detection, DBH, height, crown metrics, quantitative structure model, growth
projection) are placed in the walkable scene. This demonstrates both outputs from
one acquisition — panorama and data carrier.

*Validated against ground truth.* The inventory path is not a demonstrator. On
two TLS plots of the SegmentedForests dataset, in which every point is manually
classified, stem detection can be scored for accuracy rather than mere agreement
(recall / precision; a hit is a detection within 0.6 m of a reference stem):

| Method | plot_06 (68 stems) | plot_07 (128 stems) |
|---|--:|--:|
| own numpy baseline | 60.3 % / 42.3 % | 34.4 % / 74.6 % |
| + stem-continuity filter | 57.4 % / 70.9 % | — |
| lidR (own implementation) | 66.2 % / 45.9 % | — |
| CspStandSegmentation | 57.4 % / 27.7 % | — |
| **3DFin** (authors' configuration) | **98.5 % / 95.7 %** | **94.5 % / 100 %** |

We report the uncomfortable result openly: the established domain tool 3DFin
clearly outperforms our own baseline, consistently across both plots, and the
chain therefore uses it as the detector on plot-wide TLS clouds rather than
merely as a comparison. Because the dataset also labels shrubs, downed wood,
rocks, and stakes, it is further verifiable *what* the weaker methods detect
instead of stems — for the baseline on plot_06, half of the false alarms sit on
shrub and ground vegetation.

*Scope.* This superiority is conditional on circumferential coverage. On our own
Renon stand (median 180° arc versus 280–360° in the reference plots) 3DFin
refuses a diameter for 29 of 37 detections — correct behaviour, since the data do
not support one; a sweep over the ground-model resolution does not change this.
Our own methods still return numbers there, resting on 180° arcs — a statement
about the acquisition, not about the methods.

**Consumer/DSLR fisheye → scene (stitching).** Six overlapping fisheye frames are
stitched automatically and published as a navigable scene, demonstrating the
pose-unknown branch across the low-cost end of the device spectrum.

**Quantitative comparison against CC0 ground truth.** From each of eleven CC0
reference panoramas (Poly Haven, 8192×4096) we render synthetic captures and rebuild
a panorama (2048×1024) — once by stitching six 180° fisheye frames (pose withheld),
once by reprojecting six 90° pinhole frames plus zenith/nadir (pose used) — and
measure both against the same original.

*Counting convention (used throughout):* **completed** means the chain wrote a
panorama at all; **usable** additionally means the result is geometrically
correct. The distinction matters for stitching, where two runs produce a
complete but misregistered image.

| Branch | completed | usable | PSNR (dB) | SSIM | seam offset (px) | runtime |
|---|--:|--:|--:|--:|--:|--:|
| Stitching (pose estimated) | 8 / 11 | **6 / 11** | 22.98 ± 2.74 | 0.837 ± 0.060 | 0.14 (p95 0.53) | 14.6 s |
| Reprojection (pose known) | 11 / 11 | **11 / 11** | **26.87 ± 1.96** | **0.886 ± 0.039** | **0.10 (p95 0.23)** | 2.1 s |

Aggregate figures refer to the *usable* runs; the two misregistered stitches
(8.6 and 11.7 dB) are excluded because they would otherwise dominate mean and
spread, and are reported separately below.

The pose-based branch is better on every measure (+3.9 dB, +0.05 SSIM, a third
less local displacement) and reconstructs all eleven scenes, while stitching fails
on five: three times `enblend` aborts (excessive overlap, degenerate mask
geometry, no detectable seam) and twice a geometrically wrong panorama results
(confirmed under exhaustive search over rotation, tilt, and mirroring, staying
below 11.7 dB).

**Seam offset as an automatic quality flag.** Block-wise phase correlation against
the reference (64-px blocks, 50% overlap, low-structure blocks discarded)
separates good from failed reconstructions more sharply than PSNR or SSIM: median
seam offset 0.11–0.19 px (good stitches) and 0.07–0.13 px (reprojection) versus
5.95–6.14 px (failed stitches) — a factor of ~40, interpretable without knowing
the ground truth of a single scene, and thus a robust threshold (here > 1 px
median) for a GUI quality flag.

*Honesty of the numbers.* All synthetic captures share one nodal point; this is
the most favourable case for stitching, so the stitching figures are **upper
bounds**. No sensor noise, exposure differences, or distortion are simulated — the
geometry of the chain is measured, not camera image quality. Absolute PSNR is
capped by the resolution chain and is meaningful only in the comparison of the two
branches. The reprojection figures hold only since switching to bilinear sampling;
with nearest-neighbour sampling the same branch scored 25.4 dB / SSIM 0.871
instead of 28.2 / 0.935 (ph-mossy-forest) — an implementation artefact that could
have been reported as a property of the method.

## 4. Impact

The tool makes reproducible, self-hosted 360°/3D documentation accessible without
vendor lock-in and across the full device–cost spectrum. Two contributions are of
wider use. First, it turns the routinely discarded, pose-bearing scanner RGB
images into first-class navigable panoramas and data carriers; the evaluation
quantifies why this is preferable when pose is available (seamless, ~7× faster,
no stitching failures). Second, the seam-offset metric provides a ground-truth-free
quality signal that can gate automated batch processing. For environmental and
forest monitoring specifically, the enrichment path couples a walkable visual
record with quantitative inventory on the same acquisition, supporting
communication and revisitation of plots.

## 5. Conclusions

We presented an open-source, containerized, GUI-driven chain that converts
multi-image captures — with or without known pose — into walkable web 3D scenes,
self-hostable end to end. A ground-truth evaluation shows the pose-based
reprojection branch to be more accurate, more robust, and faster than stitching
when scanner poses are available, and yields an interpretable automatic quality
flag for the stitching branch. Future work: extend the evaluation with real
captures exhibiting nodal-point parallax; wire the quality flag into the GUI;
integrate further representations (3D Gaussian splatting, meshes) in the same
viewer; and run the prepared usability study.

## Acknowledgements

[To be completed.] Example data: Renon / ICOS IT-Ren (CC-BY-4.0); Poly Haven
panoramas (CC0).

## References

See the concept document (`Panorama_Pipeline_Konzept`) for the full reference list
(software with versions and licenses; ASTM E57; SSIM/phase-correlation; datasets;
forest/TLS methods). DOIs and years to be verified against publisher records
before submission.
