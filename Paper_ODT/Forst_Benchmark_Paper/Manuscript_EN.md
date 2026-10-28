% How much of the stem must a terrestrial laser scanner see? Diameter error as a function of circumferential coverage, and what it means for scan design
%
%

**Author:** Angel Naya, Independent Researcher, Berlin, Germany\
**Corresponding author:** Angel Naya, angel.naya@posteo.de

> DRAFT — 14 Oct 2026. References checked against Crossref/Zenodo (`lit/refs_check.md`).
> Open: Zenodo archive of the code release at submission.

## Abstract

Terrestrial laser scanning (TLS) inventories fit circles or cylinders to stem points, but occlusion
leaves each stem only partly visible. Software applies coverage rules — 3DFin accepts a
diameter only if at least 9 of 16 angular sectors (202.5°) contain points — yet the required coverage
has not been quantified. We combined a Monte Carlo experiment (six estimators, seven
perturbations), HELIOS++ simulations of three stands (400–1200 stems ha⁻¹; 26 712 stem ×
scan-configuration cases) with geometrically computed visible arc, a stand with branches at breast
height, and two open real datasets. For round stems without outliers, 45–135° of visible arc gave a
DBH RMSE ≤ 2 cm; non-circularity raised this to 180–202.5° for 40 cm stems; with outliers, only
robust estimators reached it. In simulated stands 82 % of stems were within 2 cm at 180–225° and
over 90 % beyond 225°; the 3DFin rule corresponds to a median of 190°. Branches in the breast-height
band made least-squares fits fail at any coverage, whereas RANSAC was unaffected. On 458 real stems
Kasa fitting needed about 225° for 80 % within 2 cm; with surrounding points left in, only RANSAC
approached this. Running 3DFin on twelve real plots with simulated partial coverage, 88 % of accepted
diameters were within 2 cm, but about half of the stems received a diameter with four to six
spread scan positions. Coverage thresholds must be stated per estimator and segmentation
quality, rejected stems must be reported, and scan positions should be spread rather than added.

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
towards small radii on short, noisy arcs (Kåsa, 1976; Al-Sharadqah and Chernov,
2009; Chernov, 2010). Inventory software reacts with
coverage rules. 3DFin (Laino et al., 2024) divides the cross-section into 16 sectors and
accepts a diameter only if at least nine contain points, i.e. 202.5°. In our own processing of an
open TLS plot of the ICOS site Renon (Chang et al., 2025), this rule rejected the diameter of 29 of
37 detected stems, because the median coverage of four closely spaced scan positions was 180°. On
the two Vienna Woods plots of the SegmentedForests data set (Laino et al., 2026), where median
coverage was 280–360°, the same software reached 95–100 % precision. Whether the rule was too strict
at Renon, and whether it is appropriate for other estimators, is an open question.

Abegg et al. (2017) ray-traced 2740 virtual plots derived from the Swiss national forest inventory and
showed that visibility depends on stem number, dominant diameter and the Weibull scale of the diameter
distribution, and that evenly distributed scan positions give the best visibility; they did not estimate
diameters. Gollob et al. (2019) and Ritter et al. (2020) related scanner position layout and plot size to
detection rate and diameter accuracy on real inventory plots, and FORTLS (Molina-Valero et al., 2022)
corrects stand estimates for occlusion in single-scan inventories. Li et al. (2021)
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
- **Hough**: circle Hough transform of scikit-image (`hough_circle`, default normalised accumulators;
  van der Walt et al., 2014) on a binary raster of the points, coarse-to-fine (1 cm raster over radii
  4–75 cm with the accumulator extended beyond the image, then 2.5 mm raster within ±1.5 cm of the coarse
  radius); the strongest accumulator cell is taken. No parameter was tuned.
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
cross-section is analysed. Scans were simulated with HELIOS++ 2.2.2 (Winiwarter et al., 2022)
using the RIEGL VZ-400 model (5 mm range accuracy, 0.3 mrad divergence), tripod height 1.5 m,
0.06° angular resolution, vertical field −30° to +5°. Each scene has a pool of 40 positions
(5 × 5 grid at 8 m spacing plus 15 random); each position is simulated once and the configurations
are assembled offline: n ∈ {1, 2, 3, 4, 6, 9} positions as (a) a spread grid subset (greedy max–min
from the centre), (b) 10 random draws from the pool, (c) the n positions closest to the plot centre
("clustered", as at Renon). Stem points are assigned by the HELIOS object identifier, i.e. segmentation
is perfect, isolating coverage and fitting from detection.

**Branches at breast height.** Because the stems above carry no branches, a fourth scene S1b-B repeats
S1b with identical stems, positions and scan pool and adds branches as thin tapered cylinders
(Poisson(6) per stem, attachment height 0.5–3.0 m, inclination −10° to +50°, length 0.3–2.0 m, base
diameter 1.5–5 cm). Branches belong to the stem object, so their points enter the stem point set as they
would after a real stem segmentation; in the core plot 88 % of the stems have at least one branch
crossing the 1.05–1.55 m band (median 2).

**Visible arc.** Occupied-sector counts and fine angular bins both depend on point density. We
therefore compute the geometrically visible arc: for 360 points on the true elliptical perimeter at
1.3 m, a point counts as visible from a position if it faces it (cosine of incidence > 0.1) and the line
of sight does not intersect another stem; the union over the positions of a configuration gives the
visible arc (`scripts/paperC_eval.py`). This is the CDRC of Li et al. (2021), here evaluated on the
true elliptical perimeter.

### 2.4 Metrics

Per estimator and arc class: bias, RMSE, share of stems within ±2 cm (failures counted as outside),
failure rate. A *coverage threshold* is the smallest arc from which RMSE ≤ 2 cm, |bias| ≤ 1 cm and
failure ≤ 10 % hold for all larger arcs. For the share within 2 cm we additionally report the
smallest arc class from which at least 80 % of the stems are within 2 cm, with 95 % confidence
intervals from a cluster bootstrap over stems (B = 300; all cases of a stem are resampled together
because the same stem appears in many configurations; `scripts/paperC_bootstrap.py`). The 2 cm level corresponds to the DBH accuracy of 1–2 cm that the international
TLS benchmark found achievable (Liang et al., 2018).

### 2.5 3DFin on real plots with reduced coverage

To test the complete pipeline rather than isolated circle fits, 3DFin 0.6.0 (Laino et al., 2024) was run
on the complete SegmentedForests plot clouds (12 plots, 2 cm voxel thinning) with the dataset authors'
3DFin settings (`scripts/paperC_3dfin_real.py`, GitHub Actions workflow `compute-3dfin.yml`). The run
on the full multi-scan cloud defines the reference: stems with an accepted DBH. Reduced coverage was
then produced by virtual scan positions (1, 2, 3, 4 and 6 positions spread on a grid by greedy max–min,
and 4 clustered near the plot centre) and a stem-occlusion model: a point is kept if it lies on the
facing side of its own stem and the line of sight from at least one position does not cross another
stem (all full-cloud detections act as occluders). Branches and foliage do not occlude in this model,
so coverage is, if anything, overestimated in 3DFin's favour. 3DFin was rerun with the same settings on
each reduced cloud; per reference stem we record the geometric visible arc (as in Section 2.3),
detection (a 3DFin stem within 0.5 m), acceptance (non-zero DBH) and the DBH difference to the
full-coverage 3DFin value.

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
biased), Hough from 180–247.5°. Hough tolerates outliers but not non-circularity: for DBH 40 cm it
never meets the threshold on elliptical stems (RMSE 4–7 cm even at full coverage), and below 135° it
fails in 30–65 % of cases. In the combined scenario only RANSAC (135–180°) and the Huber fit
(180–225°) reach the threshold for both diameters; Hough only for DBH 20 cm (202.5°).

### 3.2 HELIOS++: error versus visible arc

Pooled over the three stands (26 712 cases; 56, 130 and 185 core stems), the RMSE of Kasa, cylinder and
RANSAC falls from 9–17 cm below 90° to 1.6–1.7 cm at 180–225° and 0.5–0.8 cm beyond 315°; Hough remains
worst throughout (13.7 cm at 180–225°, 2.1 cm beyond 315°; Fig. 2a). The share of stems within 2 cm rises from 45–56 % at 90–135° to 82 % at
180–225°, 93 % at 225–270° and 98–99 % beyond 270° for the Kasa and cylinder fits; RANSAC stays
slightly lower beyond 225° (89–94 %) (Fig. 2b). Thicker stems need more coverage:
at 180–225° RMSE is 2.0 cm in S1a (mean DBH 37 cm) versus 1.5–1.7 cm in S1b and S1c, consistent
with the non-circularity effect in Section 3.1. A single scan position sees at most 172° of a
stem (median 164°).

**Branches at breast height (S1b-B).** With the same stems and scan positions as S1b but branches
crossing the band, the least-squares fits collapse: at 225–270° visible arc only 11 % (Kasa), 10 %
(geometric), 9 % (cylinder) and 26 % (Huber) of stems are within 2 cm, and at most 19–43 % beyond
270°; the median error above 180° is +15 to +42 cm because branch points pull the circle outwards.
RANSAC is practically unaffected (71 %, 79 % and 89 % at 135–180°, 180–225° and 225–270°, versus
73 %, 80 % and 90 % without branches). Hough degrades (43 % instead of 70 % at 225–270°); Fig. 6).

**Uncertainty of the thresholds.** The cluster bootstrap places the 80 % point of the Kasa, cylinder
and RANSAC fits in the 180–225° class for the pooled HELIOS stands (95 % CI: 180–225° to 225–270°),
of the geometric and Huber fits one class higher, and of Hough in the 270–315° class. With branches,
only RANSAC reaches 80 % (225–270° class; CI 180–225° to 225–270°).

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
were clustered, and 458 stems with ≥ 330° observed coverage (1° bins) and ≥ 300 points served as
reference; their reference DBH is the median of the Kasa, geometric, RANSAC and cylinder estimates on
all points (at least three valid; no field DBH is available). LAUT (Gollob et al., 2020a, b; CC BY 4.0): 17 Austrian inventory plots
scanned with a Faro Focus3D X330, 1 908 trees with field DBH (median 15.6 cm) and field positions; stem
points are all points within DBH/2 + 25 cm of the field position, i.e. without segmentation. Field
positions and fitted centres agree to 4 cm (median). Coverage was reduced by retaining one contiguous
arc at random orientation (5 repetitions per stem and arc). Breast-height bands were extracted with
`scripts/ext_band.py` in a GitHub Actions workflow (`.github/workflows/fetch-data.yml`).

**Stem points only** (SegmentedForests, Fig. 5a). The Kasa fit reaches 56 % of stems within 2 cm at
180°, 72 % at 202.5°, 82 % at 225° and 91 % at 270°; its RMSE falls from 6.1 cm at 135° to 2.9 cm at
202.5° and 1.5 cm at 270°, with a negative bias on short arcs (−4.4 cm at 135°, −1.0 cm at 202.5°)
as predicted by the Monte Carlo experiment. On these thinner stems (median DBH 16 cm), real bark
shifts the 80 % point from about 180° (HELIOS) to about 225°. RANSAC with a 12 mm inlier tolerance
is weaker on clean real stems (87 % at 360°), because rough bark excludes valid points. Hough reaches
only 58 % even at 360°.

**With surrounding points** (Fig. 5b, c). When branches, understorey and unlabelled points within
30 cm (SegmentedForests) or 25 cm (LAUT) remain, the least-squares fits saturate: at full coverage only
55 % (Kasa) and 64 % (geometric) of SegmentedForests stems are within 2 cm, and 35–38 % of LAUT trees
against field DBH. RANSAC rises with coverage to 84 % (SegmentedForests) and 62 % (LAUT) and is the
best estimator from about 112° on, reproducing the outlier scenario of Section 3.1 on real data. The
lower LAUT values include field-measurement error and the absence of any segmentation. Bootstrap 80 % points
(95 % CI) on SegmentedForests: Kasa 225° (225–270°), cylinder 270° (270°), geometric 270° (270–315°),
RANSAC and Huber 315° (270–315° for Huber); with surrounding points only RANSAC at 360° (315–360°);
on LAUT no estimator reaches 80 % at any arc.

### 3.5 3DFin on real plots with reduced coverage

The full-cloud runs gave 296 reference stems in 12 plots (median DBH 23.6 cm). Under reduced coverage
3DFin still detects most stems (66 % with one position, 83–96 % with two to six), but accepts a DBH for
far fewer: 10 % with one position, 24 %, 36 %, 49 % and 54 % with two, three, four and six spread
positions, and 36 % with four clustered positions, which behave like three spread ones (Fig. 7). By
visible arc, acceptance rises from 16 % at 135–180° and 36 % at 180–225° to 52–56 % at 225–315° and
76 % beyond 315°. The accepted diameters are accurate: 88 % lie within 2 cm of the full-coverage value
(66 % at 135–180°, 78 % at 180–225°, 95 % at 225–270°, ≥ 96 % beyond), and 14 % of the accepted
diameters come from stems with less than 180° visible. On real plots the sector rule thus acts as
intended — it filters poorly covered stems — but at the price of completeness: with four spread
positions half of the reference stems receive no DBH.

## 4. Discussion

**Relation to Li et al. (2021).** Their 200° CDRC guideline is confirmed for least-squares fits of clean
stem points (HELIOS: 82 % of stems within 2 cm at 180–225°), but real bark and thin stems shift the 80 %
point to about 225°, and with surrounding points no CDRC is sufficient for least-squares fits.

**Segmentation decides before coverage does.** The branch scene isolates what the real data suggested:
once non-stem points enter the band, least-squares fits fail at any coverage, while an arc-constrained
RANSAC keeps its accuracy. A coverage rule therefore only makes sense together with a statement of how
stem points were separated from branches and understorey.

**3DFin trades completeness for accuracy.** On real plots the accepted 3DFin diameters met the 2 cm level
for 78 % of stems at 180–225° and 95 % at 225–270°, close to the least-squares behaviour in HELIOS, but
3DFin withheld a DBH for about half of the stems even with four or six spread positions, and for a
quarter of the stems visible beyond 315°. Inventories that rely on the rule should therefore report the
share of stems without DBH, and scan designs should aim at more coverage than the rule's 202.5°.

**A single threshold does not fit all estimators.** Without outliers, least-squares fits need far
less than 202.5°; with non-circular stems they need about 180–200°; with outliers they never become
reliable. The threshold is therefore a property of the estimator and of the expected cross-section,
not of the data alone. The 3DFin rule is well placed for least-squares fitting of moderately
non-circular stems after good segmentation, and conservative for a robust estimator on round stems.

**Renon revisited.** With four closely spaced positions, the Renon plot reproduces the "clustered"
configuration. Our simulations predict that many of its stems lie below 180° visible arc and that
diameters fitted there carry several centimetres of error — 3DFin's refusal was therefore justified,
and estimates that our own pipeline produced for those stems should be flagged rather than reported.

**Scan design.** In line with Abegg et al. (2017), clustering wastes positions: at 1200 stems ha⁻¹, four
clustered positions (56 % of stems ≥ 180°) perform like three grid positions (58 %). A tentative recommendation, to be refined with
stand-specific simulations, is a spread grid of four to six positions per 0.16 ha (25–38 ha⁻¹) at
400–1200 stems ha⁻¹, which brought 80–98 % of stems above 180° here.

**Limitations.** In HELIOS: perfect segmentation (no detection errors), no crowns, branches only in one
scene and as simple cylinders, flat terrain, one scanner model, idealised outlier and registration models.
Range-dependent incidence effects and beam divergence are simulated by HELIOS but not varied systematically.
Hough was run with scikit-image defaults; other accumulator normalisations or smoothing may behave
differently, but no parameter was tuned for any estimator. On SegmentedForests the reference DBH is
itself a fit to well-covered points, not a field measurement. The 3DFin experiment simulates reduced coverage by
removing points from a multi-scan cloud with a stem-only occlusion model; real single-position scans
differ in point density and range effects, and its reference is 3DFin's own full-coverage result.

## 5. Conclusions

Coverage rules for TLS diameters should be reported per estimator and per segmentation quality.
With clean stem points, least-squares fits need about 180° (simulation) to 225° (real bark) of
visible arc for most stems to be within 2 cm, and 3DFin's 202.5° sector rule sits in this range.
Without clean segmentation, no amount of coverage rescues least-squares fits; robust estimators such
as RANSAC with an arc constraint are then the main lever. Scan positions should be spread rather than
clustered, especially in dense stands. Coverage rules such as 3DFin's keep the accepted diameters accurate
but leave many stems without a DBH; the share of rejected stems belongs in every TLS inventory report.

## Code availability

- Software: For3Dsuite, https://github.com/anayana/For3Dsuite (GPL-3.0-or-later). Scripts:
  `arc_error_mc.py`, `arc_error_mc_real.py`, `paperC_scene.py`, `paperC_run.py`, `paperC_pack.py`,
  `paperC_eval.py`, `paperC_figures.py`, `dbh_methods.py`.
- HELIOS++ 2.2.2 (conda-forge).
- [TODO] Archive release on Zenodo.

## Data availability

Result tables (`Paper_ODT/Forst_Benchmark_Paper/results/`) and figure sources are in the repository;
simulated scenes are reproducible from the scripts and seeds. Third-party data: Renon/ICOS IT-Ren
(Chang et al., 2025; CC BY 4.0); SegmentedForests (Laino et al., 2026; MIT); LAUT (Gollob et al., 2020b;
CC BY 4.0). Derived breast-height bands of SegmentedForests and LAUT are in `extdata/`.

## Declaration of competing interest

The author declares no competing interests.

## Figures

![**Figure 1.** Monte Carlo experiment: RMSE of DBH versus visible arc for six estimators (DBH 40 cm, 200
points, σ = 5 mm). (a) ideal circle, (b) non-circular cross-section (axis ratio 0.85–1), (c) 15 %
outliers, (d) combined perturbations. Dashed line: 2 cm; dotted line: 202.5° (3DFin sector rule).](figures/fig1_mc_rmse_vs_arc.png)

![**Figure 2.** HELIOS++ simulations, three stands pooled (26 712 stem × configuration cases). (a) RMSE of
DBH and (b) share of stems within ±2 cm (failures counted as outside) versus geometrically visible
arc.](figures/fig2_helios_error_vs_arc.png)

![**Figure 3.** Share of stems with ≥ 180° visible arc versus number of scan positions for grid, random
(mean of 10 draws) and clustered placement in stands of 400, 800 and 1200 stems ha⁻¹.](figures/fig3_design_coverage.png)

![**Figure 4.** Occupied 22.5° sectors (3DFin rule) versus geometrically visible arc in the HELIOS++
simulations; boxes show quartiles, whiskers 1.5 IQR. Dashed lines: 202.5° sector rule and 180°
visible arc.](figures/fig4_sector_vs_geometric.png){width=55%}

![**Figure 5.** Real point clouds, share of stems within ±2 cm versus retained arc. (a) SegmentedForests,
stem points only (458 stems, reference: fit on full coverage); (b) the same stems with surrounding
points within 30 cm; (c) LAUT, 460 well-covered trees against field DBH, with surrounding points within
25 cm.](figures/fig5_real_data.png)

![**Figure 6.** Effect of branches at breast height: share of stems within ±2 cm versus geometrically
visible arc in (a) stand S1b and (b) the same stand with branches crossing the 1.05–1.55 m band
(S1b-B); stem and branch points are segmented together, as after a real stem segmentation. Dotted
line: 202.5°.](figures/fig6_branches.png)

![**Figure 7.** 3DFin on twelve SegmentedForests plots with simulated reduced coverage (1–6 virtual scan
positions): share of the 296 reference stems detected and with an accepted DBH, and share of accepted
diameters within ±2 cm of the full-coverage 3DFin value, by geometrically visible arc (classes with
fewer than ten accepted diameters omitted). Dotted line: 202.5°.](figures/fig7_3dfin_real.png){width=60%}

## References

- Abegg, M., Kükenbrink, D., Zell, J., Schaepman, M.E., Morsdorf, F., 2017. Terrestrial laser scanning for forest
  inventories—tree diameter distribution and scanner location impact on occlusion. Forests 8(6), 184.
  https://doi.org/10.3390/f8060184
- Al-Sharadqah, A., Chernov, N., 2009. Error analysis for circle fitting algorithms. Electronic Journal of
  Statistics 3, 886–911. https://doi.org/10.1214/09-EJS419
- Chang, M., Candotti, A., von Ellenrieder, K., Tomelleri, E., Camurri, M., 2025. Data for: "A multi-platform
  LiDAR dataset for standardized forest inventory measurement at long term ecological monitoring sites".
  Zenodo. https://doi.org/10.5281/zenodo.17186174
- Chernov, N., 2010. Circular and Linear Regression: Fitting Circles and Lines by Least Squares. CRC Press.
- Fischler, M.A., Bolles, R.C., 1981. Random sample consensus: a paradigm for model fitting with applications to
  image analysis and automated cartography. Communications of the ACM 24(6), 381–395.
- Gollob, C., Ritter, T., Nothdurft, A., 2020a. Comparison of 3D point clouds obtained by terrestrial laser
  scanning and personal laser scanning on forest inventory sample plots. Data 5(4), 103.
  https://doi.org/10.3390/data5040103
- Gollob, C., Ritter, T., Nothdurft, A., 2020b. LAUT – Terrestrial and personal laser scanner data from Austrian
  forest inventory plots. Zenodo. https://doi.org/10.5281/zenodo.3698956
- Gollob, C., Ritter, T., Wassermann, C., Nothdurft, A., 2019. Influence of scanner position and plot size on the
  accuracy of tree detection and diameter estimation using terrestrial laser scanning on forest inventory
  plots. Remote Sensing 11(13), 1602. https://doi.org/10.3390/rs11131602
- Kåsa, I., 1976. A circle fitting procedure and its error analysis. IEEE Transactions on Instrumentation and
  Measurement IM-25(1), 8–14. https://doi.org/10.1109/TIM.1976.6312298
- Laino, D., Cabo, C., Prendes, C., Janvier, R., Ordóñez, C., Nikonovas, T., Doerr, S., Santín, C., 2024. 3DFin:
  a software for automated 3D forest inventories from terrestrial point clouds. Forestry 97(4), 479–496.
  https://doi.org/10.1093/forestry/cpae020
- Laino, D., Cabo, C., Ordóñez, C., Bolanos, R., Janvier, R., Giulioni, F., Herrmann, M., Hudak, A., Parsons, R.,
  Santín, C., 2026. SegmentedForests: a labelled dataset of terrestrial LiDAR point clouds for semantic
  segmentation of forests. Forestry 99(2). https://doi.org/10.1093/forestry/cpaf062
- Li, L., Mu, X., Soma, M., Wan, P., Qi, J., Hu, R., Zhang, W., Tong, Y., Yan, G., 2021. An iterative-mode scan
  design of terrestrial laser scanning in forests for minimizing occlusion effects. IEEE Transactions on
  Geoscience and Remote Sensing 59(4), 3547–3566. https://doi.org/10.1109/TGRS.2020.3018643
- Liang, X., Hyyppä, J., Kaartinen, H., et al., 2018. International benchmarking of terrestrial laser scanning
  approaches for forest inventories. ISPRS Journal of Photogrammetry and Remote Sensing 144, 137–179.
  https://doi.org/10.1016/j.isprsjprs.2018.06.021
- Molina-Valero, J.A., Martínez-Calvo, A., Ginzo Villamayor, M.J., Novo Pérez, M.A., Álvarez-González, J.G.,
  Montes, F., Pérez-Cruzado, C., 2022. Operationalizing the use of TLS in forest inventories: the R package
  FORTLS. Environmental Modelling & Software 150, 105337. https://doi.org/10.1016/j.envsoft.2022.105337
- Ritter, T., Gollob, C., Nothdurft, A., 2020. Towards an optimization of sample plot size and scanner position
  layout for terrestrial laser scanning in multi-scan mode. Forests 11(10), 1099. https://doi.org/10.3390/f11101099
- van der Walt, S., Schönberger, J.L., Nunez-Iglesias, J., Boulogne, F., Warner, J.D., Yager, N., Gouillart, E.,
  Yu, T., the scikit-image contributors, 2014. scikit-image: image processing in Python. PeerJ 2, e453.
  https://doi.org/10.7717/peerj.453
- Winiwarter, L., Esmorís Pena, A.M., Weiser, H., Anders, K., Martínez Sánchez, J., Searle, M., Höfle, B., 2022.
  Virtual laser scanning with HELIOS++: a novel take on ray tracing-based simulation of topographic
  full-waveform 3D laser scanning. Remote Sensing of Environment 269, 112772. https://doi.org/10.1016/j.rse.2021.112772
