% How much of the stem must a terrestrial laser scanner see? Diameter error as a function of circumferential coverage, and what it means for scan design
%
%

**Author:** Angel Naya, Independent Researcher, Berlin, Germany\
**Corresponding author:** Angel Naya, angel.naya@posteo.de

> DRAFT — 14 Oct 2026. Open items are marked **[TODO]**; references marked **[verify]** have not yet
> been checked against the original.

## Abstract

Terrestrial laser scanning (TLS) inventories estimate diameter at breast height (DBH) by fitting
circles or cylinders to stem points, but occlusion means that each stem is seen only on part of its
circumference. Software therefore applies coverage rules — 3DFin, for example, accepts a diameter only
when at least 9 of 16 angular sectors (202.5°) contain points — yet how much coverage is actually
needed, and whether one threshold suits all estimators, has not been quantified. We combine a
Monte Carlo experiment (13 arcs, six estimators, seven perturbation scenarios including non-circular
cross-sections, outliers from branches and understorey, and inter-scan registration offsets) with
HELIOS++ simulations of three stands (400, 800 and 1200 stems ha⁻¹) scanned from 40 candidate positions,
recombined offline into 216 scan configurations (26 712 stem × configuration cases). The visible arc is
computed geometrically, independent of point density. For circular stems without outliers, 90–135° of
visible arc suffices for a 2 cm RMSE; non-circularity raises this to about 180–202.5°, and with 5–15 %
outliers only RANSAC with an arc constraint stays within 2 cm, from 112.5–180°, while least-squares
fits never do, even at full coverage. In the simulated stands, 82 % of stems are within 2 cm at
180–225° visible arc and over 90 % beyond 225°. The 3DFin sector rule corresponds to a median of about
190° geometric arc and separates stems with 92 % from those with 63 % of estimates within 2 cm. Four
positions on a grid bring 80–89 % of stems above 180°; four positions clustered near the plot centre
fall to 56 % at 1200 stems ha⁻¹. On 456 labelled real stems (SegmentedForests) the Kasa fit needs about 225° for 80 % of stems within
2 cm; with the surrounding points left in, least-squares fits saturate at 55 % even at full coverage,
whereas RANSAC reaches 84 %, and 62 % against field DBH on 1 908 LAUT trees. A coverage threshold is
therefore defensible, but it must be stated per estimator, per expected stem shape and per
segmentation quality, and scan positions must be spread rather than added.

**Keywords:** terrestrial laser scanning; diameter at breast height; occlusion; circle fitting;
scan design; HELIOS++; forest inventory

## 1. Introduction

TLS has become a standard instrument for plot-level forest inventory, yet occlusion remains its main
limitation: stems hide one another, and the share of a stem's circumference that reaches the scanner
depends on stand density, diameter distribution and the placement of scan positions
(Abegg et al., 2017; Liang et al., 2018). Single-scan inventories detect markedly fewer stems than
multi-scan inventories, especially in dense, multi-layered stands (Liang et al., 2018).

Detection is only half of the problem. A stem that is detected may still be seen on a short arc, and
the diameter fitted to a short arc is poorly constrained: algebraic circle fits are known to be biased
towards small radii on short, noisy arcs (Kåsa, 1976; Chernov, 2010). Inventory software reacts with
coverage rules. 3DFin (Laino et al., 2024 [verify]) divides the cross-section into 16 sectors and
accepts a diameter only if at least nine contain points, i.e. 202.5°. In our own processing of an
open TLS plot of the ICOS site Renon (Chang et al., 2025), this rule rejected the diameter of 29 of
37 detected stems, because the median coverage of four closely spaced scan positions was 180°. On
the two Vienna Woods plots of the SegmentedForests data set (Laino et al., 2026), where median
coverage was 280–360°, the same software reached 95–100 % precision. Whether the rule was too strict
at Renon, and whether it is appropriate for other estimators, is an open question.

Abegg et al. (2017) ray-traced 2740 virtual plots derived from the Swiss national forest inventory and
showed that visibility depends on stem number, dominant diameter and the Weibull scale of the diameter
distribution, and that evenly distributed scan positions give the best visibility; they did not estimate
diameters. Other work compared diameter estimators (e.g. Hough transform versus least squares). Li et al. (2021)
introduced the cumulative degree of ring closure (CDRC) — the union of the angular sectors of a stem
circle that are visible from the scan positions — to optimise scan positions in HELIOS-simulated
forests, and noted that accurate DBH estimation requires a CDRC above about 200°. That statement rests
on one least-squares estimator, idealised segmentation and simulated stems. How the threshold depends
on the estimator, on non-circular stems, on outliers from branches and understorey, and whether it holds
for real bark and field-measured DBH, has to our knowledge not been quantified, nor has it been related
to the sector rules used in inventory software.

We ask: (i) how does the DBH error of common estimators depend on visible arc, and how is this
modified by non-circular stems, outliers and registration offsets; (ii) does a sector-based rule
such as 3DFin's correspond to a meaningful coverage threshold; and (iii) which scan designs achieve
that coverage in stands of different density?

## 2. Methods

### 2.1 Estimators

All estimators operate on the points of one stem in the band 1.05–1.55 m (cylinder: 1.0–1.6 m):

- **Kasa**: algebraic least-squares circle (Kåsa, 1976).
- **Geometric**: least-squares circle minimising orthogonal distances (Gauss–Newton, bounded centre
  ±0.3 m and radius 4–75 cm; Kasa start).
- **RANSAC**: three-point circle hypotheses (400 iterations, 12 mm inlier tolerance); a hypothesis is
  admitted only if its inliers span at least 90°; final Kasa fit on the inliers (Fischler and Bolles, 1981).
- **Cylinder**: circle fit in the plane normal to an axis whose tilt is optimised (Nelder–Mead,
  ≤ 15°), to remove the elliptical bias of tilted stems.
- **Hough**: circle Hough transform with normal-directed voting; normals from local PCA (k = 12) after
  1 cm thinning; 5 mm accumulator, 3 × 3 smoothing, radius coarse-to-fine (1 cm, 2 mm).
- **Huber-robust**: geometric fit with Huber loss (scale 1 cm), Kasa start.

Implementations: `scripts/dbh_methods.py`, `scripts/arc_error_mc_real.py` (repository, Section *Code
availability*). The 3DFin acceptance rule is evaluated as the number of occupied 22.5° sectors around
the stem centre in a 10 cm slice at 1.3 m.

### 2.2 Monte Carlo experiment

A stem of DBH 20 or 40 cm is observed on one contiguous arc θ ∈ {45, 67.5, …, 360°} with N = 200 or
1000 points uniformly distributed over the arc and a 0.6 m height band, radial Gaussian noise σ = 5 mm
(2 and 10 mm in the ideal case). Seven scenarios: *ideal*; *non-circular* (elliptical cross-section,
axis ratio U(0.85, 1), random orientation; true DBH = perimeter/π, tape definition); *5 % / 15 %
outliers* (points 2–30 cm outside the surface, as from twigs, foliage or understorey in front of the
stem); *5 / 10 mm registration offset* (the second half of arcs > 90° shifted, mimicking a second scan
position); *combined* (non-circular + 5 % outliers + 5 mm offset). 100 replicates per cell (300 for the
ideal grid). The Cramér–Rao lower bound for the radius under the ideal model is reported as a
reference for the best achievable precision. Code: `scripts/arc_error_mc.py`, `scripts/arc_error_mc_real.py`.

### 2.3 HELIOS++ simulation

Three 40 × 40 m core plots with a 10 m buffer were generated (`scripts/paperC_scene.py`): S1a
400 stems ha⁻¹ (DBH 38 ± 11 cm), S1b 800 ha⁻¹ (30 ± 9 cm), S1c 1200 ha⁻¹ (24 ± 7 cm); random positions
with a minimum gap of 10 cm. Stems are 4 m elliptical cylinders (axis ratio U(0.85, 1), 32 segments,
rings every 0.25 m with ±3 mm bark roughness); crowns were omitted because only the breast-height
cross-section is analysed. Scans were simulated with HELIOS++ 2.2.2 (Winiwarter et al., 2022 [verify])
using the RIEGL VZ-400 model (5 mm range accuracy, 0.3 mrad divergence), tripod height 1.5 m,
0.06° angular resolution, vertical field −30° to +5°. Each scene has a pool of 40 positions
(5 × 5 grid at 8 m spacing plus 15 random); each position is simulated once and the configurations
are assembled offline: n ∈ {1, 2, 3, 4, 6, 9} positions as (a) a spread grid subset (greedy max–min
from the centre), (b) 10 random draws from the pool, (c) the n positions closest to the plot centre
("clustered", as at Renon). Stem points are assigned by the HELIOS object identifier, i.e. segmentation
is perfect, isolating coverage and fitting from detection.

**Visible arc.** Occupied-sector counts and fine angular bins both depend on point density. We
therefore compute the geometrically visible arc: for 360 points on the true elliptical perimeter at
1.3 m, a point counts as visible from a position if it faces it (cosine of incidence > 0.1) and the line
of sight does not intersect another stem; the union over the positions of a configuration gives the
visible arc (`scripts/paperC_eval.py`). This is the CDRC of Li et al. (2021), here evaluated on the
true elliptical perimeter.

### 2.4 Metrics

Per estimator and arc class: bias, RMSE, share of stems within ±2 cm (failures counted as outside),
failure rate. A *coverage threshold* is the smallest arc from which RMSE ≤ 2 cm, |bias| ≤ 1 cm and
failure ≤ 10 % hold for all larger arcs. The 2 cm level follows common inventory accuracy targets
[TODO: cite a national inventory tolerance].

## 3. Results

### 3.1 Monte Carlo

Under the ideal model all least-squares estimators approach the Cramér–Rao bound for arcs ≥ 135°.
On short arcs the Kasa, RANSAC and cylinder fits are biased low (DBH 40 cm, N = 200: −2.4 cm at 90°,
−7.1 cm at 67.5°), whereas the geometric fit stays unbiased (RMSE 0.8 cm at 90°); coverage thresholds
are 45–135° depending on estimator, noise and N (Fig. 1a).

Non-circularity shifts the thresholds of all estimators to about 180–202.5° for DBH 40 cm and to
90–135° for DBH 20 cm: a partial view of an ellipse yields a systematically wrong circle, an error
that grows with diameter (Fig. 1b). Registration offsets of 5–10 mm set an RMSE floor of 0.5–0.9 cm
but barely change thresholds.

Outliers dominate everything else (Fig. 1c). With 5–15 % outliers, Kasa, geometric and cylinder fits
never meet the threshold, even at 360° (RMSE 2–7 cm). RANSAC meets it from 112.5–135°, the
Huber-robust fit only from 135–270° (it fails on short arcs because its Kasa starting value is already
biased), Hough from 180–225°. In the combined scenario only RANSAC (135–180°), the Huber fit
(180–225°) and, partly, Hough (225–315°) reach the threshold.

### 3.2 HELIOS++: error versus visible arc

Pooled over the three stands (26 712 cases; 56, 130 and 185 core stems), the RMSE of Kasa, cylinder and
RANSAC falls from 9–17 cm below 90° to 1.6–1.7 cm at 180–225° and 0.5–0.9 cm beyond 315°; Hough remains
worst throughout (Fig. 2a). The share of stems within 2 cm rises from 45–56 % at 90–135° to 82 % at
180–225°, 93 % at 225–270° and 98–99 % beyond 270° (Fig. 2b). Thicker stems need more coverage:
at 180–225° RMSE is 2.0 cm in S1a (mean DBH 37 cm) versus 1.5–1.7 cm in S1b and S1c, consistent
with the non-circularity effect in Section 3.1. A single scan position sees at most 172° of a
stem (median 164°).

### 3.3 Sector rule and scan design

The 3DFin rule of ≥ 9/16 sectors corresponds to a median geometric arc of 190° at exactly nine sectors
(Fig. 4); 7.2 % of accepted stems have less than 180° visible. Used as an acceptance filter, the rule
separates stems with 92 % (Kasa) of estimates within 2 cm from those with 63 % — it sits close to the
arc at which errors become small in these simulations.

Coverage depends more on the spread than on the number of positions (Fig. 3). Four grid positions
bring 89 %, 82 % and 80 % of stems above 180° in the three stands; six bring 96–98 %. Four positions
clustered near the centre reach 89 %, 71 % and 56 %, i.e. the penalty of clustering grows with stand
density. Random placement performs close to the grid.

### 3.4 Real point clouds

**Data.** SegmentedForests (Laino et al., 2026; MIT): 12 of 14 TLS plots with point-wise semantic labels
(plot 08 omitted for size, plot 09 failed to download); stem points (class 3) at 1.0–1.6 m above ground
were clustered, and 456 stems with ≥ 330° observed coverage (1° bins) and ≥ 300 points served as
reference; their reference DBH is the median of the four least-squares/RANSAC estimates on all points
(no field DBH is available). LAUT (Gollob et al., 2020 [verify]; CC BY 4.0): 17 Austrian inventory plots
scanned with a Faro Focus3D X330, 1 908 trees with field DBH (median 15.6 cm) and field positions; stem
points are all points within DBH/2 + 25 cm of the field position, i.e. without segmentation. Field
positions and fitted centres agree to 4 cm (median). Coverage was reduced by retaining one contiguous
arc at random orientation (5 repetitions per stem and arc). Breast-height bands were extracted with
`scripts/ext_band.py` in a GitHub Actions workflow (`.github/workflows/fetch-data.yml`).

**Stem points only** (SegmentedForests, Fig. 5a). The Kasa fit reaches 56 % of stems within 2 cm at
180°, 73 % at 202.5°, 82 % at 225° and 91 % at 270°; its RMSE falls from 6.1 cm at 135° to 2.9 cm at
202.5° and 1.5 cm at 270°, with a negative bias on short arcs (−4.4 cm at 135°, −1.0 cm at 202.5°)
as predicted by the Monte Carlo experiment. On these thinner stems (median DBH 16 cm), real bark
shifts the 80 % point from about 180° (HELIOS) to about 225°. RANSAC with a 12 mm inlier tolerance
is weaker on clean real stems (88 % at 360°), because rough bark excludes valid points.

**With surrounding points** (Fig. 5b, c). When branches, understorey and unlabelled points within
30 cm (SegmentedForests) or 25 cm (LAUT) remain, the least-squares fits saturate: at full coverage only
55 % (Kasa) and 64 % (geometric) of SegmentedForests stems are within 2 cm, and 35–38 % of LAUT trees
against field DBH. RANSAC rises with coverage to 84 % (SegmentedForests) and 62 % (LAUT) and is the
best estimator from about 112° on, reproducing the outlier scenario of Section 3.1 on real data. The
lower LAUT values include field-measurement error and the absence of any segmentation.

## 4. Discussion

**Relation to Li et al. (2021).** Their 200° CDRC guideline is confirmed for least-squares fits of clean
stem points (HELIOS: 82 % of stems within 2 cm at 180–225°), but real bark and thin stems shift the 80 %
point to about 225°, and with surrounding points no CDRC is sufficient for least-squares fits.

**A single threshold does not fit all estimators.** Without outliers, least-squares fits need far
less than 202.5°; with non-circular stems they need about 180–200°; with outliers they never become
reliable. The threshold is therefore a property of the estimator and of the expected cross-section,
not of the data alone. The 3DFin rule is well placed for least-squares fitting of moderately
non-circular stems after good segmentation, and conservative for a robust estimator on round stems.

**Renon revisited.** With four closely spaced positions, the Renon plot reproduces the "clustered"
configuration. Our simulations predict that many of its stems lie below 180° visible arc and that
diameters fitted there carry several centimetres of error — 3DFin's refusal was therefore justified,
and estimates that our own pipeline produced for those stems should be flagged rather than reported.

**Scan design.** In line with Abegg et al. (2017), clustering wastes positions: at 1200 stems ha⁻¹, four clustered positions (56 % of
stems ≥ 180°) perform like three grid positions (58 %). A tentative recommendation, to be refined with
stand-specific simulations, is a spread grid of four to six positions per 0.16 ha (25–38 ha⁻¹) at
400–1200 stems ha⁻¹, which brought 80–98 % of stems above 180° here.

**Limitations.** Perfect segmentation (no detection errors), no branches or crowns at breast height
in HELIOS, flat terrain, one scanner model, idealised outlier and registration models. Range-dependent incidence effects and beam divergence are simulated
by HELIOS but not varied systematically. The Hough implementation (normal voting, 5 mm accumulator)
performed worst throughout and may understate what tuned Hough variants achieve. On SegmentedForests
the reference DBH is itself a fit to well-covered points, not a field measurement.

## 5. Conclusions

Coverage rules for TLS diameters should be reported per estimator and per segmentation quality.
With clean stem points, least-squares fits need about 180° (simulation) to 225° (real bark) of
visible arc for most stems to be within 2 cm, and 3DFin's 202.5° sector rule sits in this range.
Without clean segmentation, no amount of coverage rescues least-squares fits; robust estimators such
as RANSAC with an arc constraint are then the main lever. Scan positions should be spread rather than
clustered, especially in dense stands.

## Code availability

- Software: For3Dsuite, https://github.com/anayana/For3Dsuite (GPL-3.0-or-later). Scripts:
  `arc_error_mc.py`, `arc_error_mc_real.py`, `paperC_scene.py`, `paperC_run.py`, `paperC_pack.py`,
  `paperC_eval.py`, `paperC_figures.py`, `dbh_methods.py`.
- HELIOS++ 2.2.2 (conda-forge).
- [TODO] Archive release on Zenodo.

## Data availability

Result tables (`Paper_ODT/Forst_Benchmark_Paper/results/`) and figure sources are in the repository;
simulated scenes are reproducible from the scripts and seeds. Third-party data: Renon/ICOS IT-Ren
(Chang et al., 2025; CC BY 4.0); SegmentedForests (Laino et al., 2026; MIT).

## Declaration of competing interest

The author declares no competing interests.

## References

- Abegg, M., Kükenbrink, D., Zell, J., Schaepman, M.E., Morsdorf, F., 2017. Terrestrial laser scanning for
  forest inventories—tree diameter distribution and scanner location impact on occlusion. Forests 8(6), 184.
- Chang, … 2025. [TODO: full Renon/ICOS data reference, Zenodo 17186174]
- Chernov, N., 2010. Circular and Linear Regression: Fitting Circles and Lines by Least Squares. CRC Press.
- Fischler, M.A., Bolles, R.C., 1981. Random sample consensus. Communications of the ACM 24(6), 381–395.
- Gollob, C., Ritter, T., Nothdurft, A., 2020. Comparison of 3D point clouds obtained by terrestrial laser
  scanning and personal laser scanning on forest inventory sample plots. Data 5(4), 103. [verify authors]
- Kåsa, I., 1976. A circle fitting procedure and its error analysis. IEEE Transactions on Instrumentation and
  Measurement IM-25(1), 8–14.
- Laino, D., Cabo, C., Prendes, C., et al., 2024. 3DFin: a software for automated 3D forest inventories from
  terrestrial point clouds. Forestry. [verify]
- Laino, D., Cabo, C., Ordóñez, C., et al., 2026. SegmentedForests. Forestry 99(2); doi:10.1093/forestry/cpaf062.
- Li, L., Mu, X., Soma, M., Wan, P., Qi, J., Hu, R., Zhang, W., Tong, Y., Yan, G., 2021. An iterative-mode
  scan design of terrestrial laser scanning in forests for minimizing occlusion effects. IEEE Transactions
  on Geoscience and Remote Sensing [verify volume/pages; accepted Aug 2020].
- Liang, X., Hyyppä, J., Kaartinen, H., et al., 2018. International benchmarking of terrestrial laser
  scanning approaches for forest inventories. ISPRS Journal of Photogrammetry and Remote Sensing 144, 137–179.
- Molina-Valero, J.A., et al., 2022. FORTLS: an R package for processing TLS data and estimating stand
  variables in forest inventories. Environmental Modelling & Software 150, 105337.
- Weiser, H., Schäfer, J., Winiwarter, L., et al., 2022. Individual tree point clouds and tree measurements
  from multi-platform laser scanning in German forests. Earth System Science Data 14, 2989–3012. [verify title]
- Winiwarter, L., Esmorís Pena, A.M., Weiser, H., et al., 2022. Virtual laser scanning with HELIOS++.
  Remote Sensing of Environment 269, 112772. [verify]
