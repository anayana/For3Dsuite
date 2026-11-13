---
title: "How much of the stem must a terrestrial laser scanner see? Diameter error as a function of circumferential coverage, and what it means for scan design"
---

Angel Naya^a^

^a^ Independent Researcher, Berlin, Germany

Corresponding author: Angel Naya, Berlin, Germany. E-mail: angel.naya@posteo.de

## Abstract[^abbr]

[^abbr]: Abbreviations: CDRC, cumulative degree of ring closure; DBH, diameter at breast height; MLS, mobile laser scanning; PLS, personal laser scanning; RANSAC, random sample consensus; RMSE, root mean square error; SLAM, simultaneous localization and mapping; TLS, terrestrial laser scanning.

Stem diameters at breast height (DBH) are derived from terrestrial laser scanning (TLS) data by fitting circles or cylinders
to stem points, but occlusion leaves each stem partly hidden. Algorithms apply coverage rules — 3DFin accepts a
diameter only if at least 9 of 16 angular sectors (202.5°) contain points — yet the required coverage
has not been quantified. We combined a Monte Carlo experiment (six estimators, seven
perturbations), HELIOS++ simulations of three stands (400–1200 stems ha⁻¹) with geometrically computed visible arc, a stand with branches at breast
height, and two open real datasets. For round stems without outliers, 45–180° of visible arc gave a
DBH root mean square error (RMSE) ≤ 2 cm; non-circularity raised this to 157.5–202.5° for 40 cm stems; with outliers, only
robust estimators reached it. In simulated stands 82 % of stems were within 2 cm at 180–225° and
over 90 % beyond 225°; the 3DFin rule corresponds to a median of 190°. Branches in the breast-height
band made least-squares fits fail at any coverage, whereas random sample consensus (RANSAC) fitting was unaffected. On 458 real stems
Kasa fitting needed 225° for 80 % within 2 cm; with surrounding points left in, only RANSAC
approached this. Running 3DFin on twelve real plots with partial coverage, 88 % of accepted
diameters were within 2 cm, but about half the stems received a diameter with four to six
spread scan positions. Coverage thresholds must be stated per estimator and segmentation
quality, rejected stems must be reported, and scan positions should be spread rather than added.

**Keywords:** Terrestrial laser scanning; Diameter at breast height; Occlusion; Circle fitting; Virtual laser scanning; Scan design

## 1. Introduction

Terrestrial laser scanning (TLS) was introduced to forestry in the early 2000s for basic tree
measurements such as height and diameter and has since become a tool for detailed three-dimensional
assessment of forest structure (Calders et al., 2020). In forest inventories, TLS records plot-level
point clouds with millimetre detail from which attributes such as stem position and diameter at
breast height (DBH) can be derived automatically and repeatedly (Liang et al., 2016). An international
benchmark of 18 algorithms applied to identical TLS data showed large differences in accuracy between
methods and forest conditions (Liang et al., 2018), and the operational use of TLS in national forest
inventories is still being evaluated (Holvoet et al., 2025).

The main limitation of static TLS is occlusion. Stems, branches and understorey hide parts of the plot
from each scan position, so that the share of a stem's circumference that reaches the scanner depends on
stand density, the diameter distribution and the placement of the scanner (Abegg et al., 2017). In a
comparison across a wide range of forest types and structures, no tree was scanned around its whole
cross-section at 1.3 m in single-scan mode and 42 % of the trees in multi-scan mode (Bauwens et al.,
2016). The proportion of detected trees decreases with distance from the scanner, following the
decrease of visible area (Olofsson et al., 2014), and single-scan data yield markedly fewer detected
stems than multi-scan data, particularly in dense, multi-layered stands (Liang et al., 2018). Scan
protocols therefore trade coverage against field time; for plot-scale structural modelling, a
10 m × 10 m scan grid has been recommended at a cost of several field days per hectare (Wilkes et al.,
2017).

Mobile laser scanning (MLS), from vehicles, backpacks or hand-held personal laser scanners (PLS),
records the stand along a continuous trajectory and thereby reduces occlusion (Bauwens et al., 2016;
Bienert et al., 2018). A hand-held scanner recorded the full cross-section of 91 % of the trees in the
comparison mentioned above (Bauwens et al., 2016), PLS detected more trees than TLS on inventory plots
(Gollob et al., 2020c), and hand-held scanning shortened survey time considerably compared with static
scanning and conventional fieldwork (Ryding et al., 2015). Since the first demonstrations of personal
laser scanning in forests (Liang et al., 2014), backpack, hand-held and under-canopy drone systems have
been compared for field reference data (Hyyppä et al., 2020), low-cost devices have been tested as TLS
alternatives (Mokroš et al., 2021), and hand-held PLS has been reviewed with a view to operational
inventories (Balenović et al., 2021). Mobile systems do not, however, remove the question of coverage.
Their coverage is governed by the trajectory, and the density of walking lines affected single-tree
estimates from hand-held scanning (Del Perugia et al., 2019). Simulations of hand-held trajectories in
complex natural forests showed that occlusion by the surrounding vegetation reduces the point density on
stems, lowers detection and increases DBH errors, which makes trajectory design a question of coverage
as well (Kuželka, 2025). In all ground-based point clouds, the
diameter of a stem is estimated from the part of its circumference that was recorded.

The diameter fitted to a partial arc is poorly constrained. Algebraic circle fits are biased towards
small radii on short, noisy arcs (Kåsa, 1976; Al-Sharadqah and Chernov, 2009; Chernov, 2010), and both
the scan mode and the circle-fitting method affect stem detection and diameter estimates (Pueschel et
al., 2013). Robust approaches such as random sample consensus (RANSAC) reduce the influence of noise (Olofsson et al., 2014).
Processing software reacts with coverage rules. 3DFin (Laino et al., 2024) divides the stem
cross-section into 16 angular sectors and accepts a diameter only if at least nine sectors contain
points, i.e. 202.5° of the circumference, while FORTLS (Molina-Valero et al., 2022) corrects stand-level
estimates for occlusion in single-scan inventories.

Previous work has addressed coverage mainly in terms of visibility and detection. Abegg et al. (2017)
ray-traced 2740 virtual plots derived from the Swiss national forest inventory and showed that
visibility depends on stem number, dominant diameter and the scale of the diameter distribution, and
that evenly distributed scan positions give the best visibility; they did not estimate diameters.
Gollob et al. (2019) and Ritter et al. (2020) related scanner position layout and plot size to detection
rate and diameter accuracy on real inventory plots. Li et al. (2021) introduced the cumulative degree of
ring closure (CDRC), the union of the angular sectors of a stem circle that are visible from the scan
positions, to optimise scan positions in simulated forests, and noted that accurate DBH estimation
requires a CDRC above about 200°. That statement rests on one least-squares estimator, idealised
segmentation and simulated stems. How the required coverage depends on the estimator, on non-circular
stems and on outliers from branches and understorey, whether it holds for real bark and field-measured
DBH, and how it relates to the sector rules used in inventory software has, to our knowledge, not been
quantified.

This study therefore asks: (i) how does the DBH error of common estimators depend on the visible arc,
and how is this modified by non-circular stems, outliers, branches and registration offsets; (ii) does
a sector-based rule such as that of 3DFin correspond to a meaningful coverage threshold, and what does
it cost in completeness; and (iii) which scan designs achieve the required coverage in stands of
different density? We combine three levels of evidence: a Monte Carlo experiment in which coverage,
cross-section shape, outliers and registration errors are controlled; virtual laser scanning of three
simulated stands and of one stand with branches at breast height with HELIOS++ (Winiwarter et al.,
2022), in which the visible arc of every stem is known geometrically; and two open real datasets,
including a run of 3DFin itself on twelve real plots with simulated partial coverage.

## 2. Methods

### 2.1 Estimators

All estimators operate on the points $(x_i, y_i)$, $i = 1, \dots, N$, of one stem in the band
1.05–1.55 m above ground (the cylinder fit uses 1.0–1.6 m); the height coordinate is ignored except by
the cylinder fit. The DBH is reported as twice the fitted radius. Six estimators that are common in
TLS processing or represent distinct statistical principles were compared.

*Kasa fit.* The algebraic circle fit of Kåsa (1976) writes the circle as
$x^2 + y^2 + Dx + Ey + F = 0$ and minimises the algebraic residuals

$$\min_{D,E,F} \sum_{i=1}^{N} \left(x_i^2 + y_i^2 + D x_i + E y_i + F\right)^2, \qquad (1)$$

which is a linear least-squares problem with centre $(a, b) = (-D/2, -E/2)$ and radius
$r = \sqrt{a^2 + b^2 - F}$. It is fast and needs no start value, but its implicit weighting of the
residuals biases the radius towards small values when the points cover only a short, noisy arc
(Al-Sharadqah and Chernov, 2009; Chernov, 2010).

*Geometric fit.* The geometric fit minimises the orthogonal distances of the points to the circle,

$$\min_{a,b,r} \sum_{i=1}^{N} \left(\sqrt{(x_i - a)^2 + (y_i - b)^2} - r\right)^2, \qquad (2)$$

solved iteratively from the Kasa solution with the centre bounded to ±0.3 m around the start and the
radius to 4–75 cm; a solution on a bound is treated as a failure.

*RANSAC.* Circle hypotheses are formed from three randomly drawn points (400 iterations), and points
within 12 mm of a hypothesis count as inliers (Fischler and Bolles, 1981). A hypothesis is admitted only
if its inliers span at least 90° around its centre, which prevents small circles through dense clusters
of points on a short arc from winning; the final estimate is a Kasa fit to the inliers of the best
admitted hypothesis.

*Cylinder fit.* The axis direction is optimised (Nelder–Mead, tilt limited to 15°) so that the circle
fitted in the plane normal to the axis has minimal residual spread; this removes the elliptical
distortion that a tilted stem produces in a horizontal slice. A solution at the tilt limit is treated as
a failure.

*Huber-robust fit.* The geometric objective (2) is replaced by the Huber loss of the orthogonal
residuals $e_i$,

$$\rho(e) = \begin{cases} e^2/2, & |e| \le c \\ c\,(|e| - c/2), & |e| > c \end{cases} \qquad (3)$$

with $c = 1$ cm, so that residuals larger than the scale enter linearly instead of quadratically; start
values and bounds as for the geometric fit.

*Hough transform.* The circle Hough transform of scikit-image (`hough_circle` with normalised
accumulators; van der Walt et al., 2014) is applied to a binary raster of the points, coarse-to-fine:
first on a 1 cm raster over radii of 4–75 cm, with the accumulator extended beyond the image so that
centres of short arcs may lie outside the point extent, then on a 2.5 mm raster within ±1.5 cm of the
coarse radius. The strongest accumulator cell is taken.

No parameter of any estimator was tuned to the data. Implementations: `dbh_methods.py` and
`arc_error_mc_real.py` (Naya, 2026; see Data availability). For comparison with inventory software, the 3DFin
acceptance rule is evaluated as the number of occupied 22.5° sectors around the stem centre in a 10 cm
slice at 1.3 m.

### 2.2 Monte Carlo experiment

A stem of DBH 20 or 40 cm is observed on one contiguous arc θ ∈ {45, 67.5, …, 360°} with N = 200 or
1000 points uniformly distributed over the arc and a 0.6 m height band, radial Gaussian noise σ = 5 mm
(2 and 10 mm in the ideal case). Seven scenarios: *ideal*; *non-circular* (elliptical cross-section,
axis ratio U(0.85, 1), random orientation; true DBH = perimeter/π, tape definition); *5 % / 15 %
outliers* (points 2–30 cm outside the surface, as from twigs, foliage or understorey in front of the
stem); *5 / 10 mm registration offset* (the second half of arcs > 90° shifted, mimicking a second scan
position); *combined* (non-circular + 5 % outliers + 5 mm offset). 100 replicates per cell (300 for the
ideal grid). As a reference for the best achievable precision, the Cramér–Rao lower bound for
the radius is computed for the ideal model. With the residual derivatives
$\mathbf{g}_i = (-\cos\varphi_i, -\sin\varphi_i, -1)$ with respect to $(a, b, r)$ at the point angles
$\varphi_i$ spread uniformly over the arc, the Fisher information is

$$\mathbf{J} = \sigma^{-2} \sum_{i=1}^{N} \mathbf{g}_i^{\mathsf T} \mathbf{g}_i, \qquad
\mathrm{SD}(\hat r) \ge \sqrt{\left(\mathbf{J}^{-1}\right)_{33}}. \qquad (4)$$

The bound grows rapidly as the arc shortens, because the centre and the radius become nearly
interchangeable on a short arc. Code: `scripts/arc_error_mc.py`, `scripts/arc_error_mc_real.py`.

### 2.3 HELIOS++ simulation

Three 40 × 40 m core plots with a 10 m buffer were generated (`scripts/paperC_scene.py`): S1a
400 stems ha⁻¹ (DBH drawn from 38 ± 11 cm), S1b 800 ha⁻¹ (30 ± 9 cm), S1c 1200 ha⁻¹ (24 ± 7 cm); random positions
with a minimum gap of 10 cm. Stems are 4 m elliptical cylinders (axis ratio U(0.85, 1), 32 segments,
rings every 0.25 m with ±3 mm bark roughness); crowns were omitted because only the breast-height
cross-section is analysed. Scans were simulated with HELIOS++ 2.2.2 (Winiwarter et al., 2022)
using the RIEGL VZ-400 model (5 mm range accuracy, 0.3 mrad divergence), tripod height 1.5 m,
0.06° angular resolution, vertical field −30° to +5°. Each scene has a pool of 40 positions
(5 × 5 grid at 8 m spacing plus 15 random); each position is simulated once and the configurations
are assembled offline: n ∈ {1, 2, 3, 4, 6, 9} positions as (a) a spread grid subset (greedy max–min
from the centre), (b) 10 random draws from the pool, (c) the n positions closest to the plot centre
("clustered"). Stem points are assigned by the HELIOS object identifier, i.e. segmentation
is perfect, isolating coverage and fitting from detection.

The stems of S1a–S1c carry no branches. To test the effect of branches at breast height, a
fourth scene S1b-B repeats S1b with identical stems, positions and scan pool and adds branches as thin tapered cylinders
(Poisson(6) per stem, attachment height 0.5–3.0 m, inclination −10° to +50°, length 0.3–2.0 m, base
diameter 1.5–5 cm). Branches belong to the stem object, so their points enter the stem point set as they
would after a real stem segmentation; in the core plot 88 % of the stems have at least one branch
crossing the 1.05–1.55 m band (median 2).

Occupied-sector counts and fine angular bins both depend on point density. As a density-independent
measure of coverage we therefore compute the geometrically visible arc: for 360 points on the true elliptical perimeter at
1.3 m, a point counts as visible from a position if it faces it (cosine of incidence > 0.1) and the line
of sight does not intersect another stem; the union over the positions of a configuration gives the
visible arc (`scripts/paperC_eval.py`). Formally, with $v_k(\psi) \in \{0, 1\}$ indicating whether the
perimeter point at angle $\psi$ is visible from position $k$, the visible arc of a configuration $K$ is

$$\theta_{\mathrm{vis}} = \frac{360^\circ}{360} \sum_{j=1}^{360} \max_{k \in K} v_k(\psi_j). \qquad (5)$$ This is the CDRC of Li et al. (2021), here evaluated on the
true elliptical perimeter.

### 2.4 Real point clouds

Two open datasets were used. SegmentedForests (Laino et al., 2026; MIT licence) provides TLS point
clouds of 14 plots with point-wise semantic labels; 12 plots were used (plot 08 was omitted because of
its size, plot 09 could not be downloaded). Stem points (class 3) at 1.0–1.6 m above ground were
clustered into stems, and 458 stems with at least 330° observed coverage (1° bins) and at least 300
points served as references. As no field DBH is available, the reference DBH of each stem is the median
of the Kasa, geometric, RANSAC and cylinder estimates on all of its points (at least three valid).
LAUT (Gollob et al., 2020a, b; CC BY 4.0) contains TLS scans (Faro Focus3D X330) of 17 Austrian
inventory plots with field-measured DBH (1 908 trees, median 15.6 cm) and tree positions. Here all
points within DBH/2 + 25 cm of the field position were taken as the stem's points, i.e. without any
segmentation; field positions and fitted centres agree to 6 cm (median). Breast-height bands were
extracted with `ext_band.py`.

In both datasets, coverage was reduced artificially for well-covered stems by retaining one contiguous
arc at random orientation (12 arcs from 45° to 360° for SegmentedForests; 7 arcs from 90° to 360° for
the 460 LAUT trees with at least 330° observed coverage; 5 repetitions each), and the six estimators
were applied to the retained points. For SegmentedForests this was done with the stem points only and,
in a second variant, with all non-stem points within 30 cm of the stem surface added, as from branches
and understorey.

### 2.5 3DFin on real plots with reduced coverage

To test the complete pipeline rather than isolated circle fits, 3DFin 0.6.0 (Laino et al., 2024) was run
on the complete SegmentedForests plot clouds (12 plots, 2 cm voxel thinning) with the dataset authors'
3DFin settings (`paperC_3dfin_real.py`). The run
on the full multi-scan cloud defines the reference: stems with an accepted DBH. Reduced coverage was
then produced by virtual scan positions (1, 2, 3, 4 and 6 positions spread on a grid by greedy max–min,
and 4 clustered near the plot centre) and a stem-occlusion model: a point is kept if it lies on the
facing side of its own stem and the line of sight from at least one position does not cross another
stem (all full-cloud detections act as occluders). Branches and foliage do not occlude in this model,
so coverage is, if anything, overestimated in 3DFin's favour. 3DFin was rerun with the same settings on
each reduced cloud; per reference stem we record the geometric visible arc (as in Section 2.3),
detection (a 3DFin stem within 0.5 m), acceptance (non-zero DBH) and the DBH difference to the
full-coverage 3DFin value.

### 2.6 Metrics

For each estimator and class of visible arc, the error of a DBH estimate is
$e = \widehat{\mathrm{DBH}} - \mathrm{DBH}_{\mathrm{ref}}$, where the reference is the true perimeter-based
DBH in the simulations, the full-coverage estimate on SegmentedForests and the field measurement on
LAUT. Bias and root mean square error (RMSE) are computed over all successful estimates,

$$\mathrm{bias} = \frac{1}{n} \sum e_j, \qquad \mathrm{RMSE} = \sqrt{\frac{1}{n} \sum e_j^2}, \qquad (6)$$

and the failure rate is the share of cases in which an estimator returned no value. The share of stems
within ±2 cm counts failures as outside, so that an estimator cannot improve its score by refusing
difficult stems. The 2 cm level corresponds to the DBH accuracy of 1–2 cm that the international TLS
benchmark found achievable (Liang et al., 2018).

In the Monte Carlo experiment, a *coverage threshold* is the smallest arc from which RMSE ≤ 2 cm,
|bias| ≤ 1 cm and failure ≤ 10 % hold for all larger arcs. For the share within 2 cm we additionally
report the smallest arc class from which at least 80 % of the stems are within 2 cm. Because the same
stem appears in many scan configurations and arc reductions, cases are not independent; 95 %
confidence intervals for the shares and for the 80 % point were therefore obtained by a cluster
bootstrap that resamples stems with replacement and keeps all cases of a drawn stem together
(B = 300; `scripts/paperC_bootstrap.py`).

## 3. Results

### 3.1 Monte Carlo

Under the ideal model all least-squares estimators approach the Cramér–Rao bound for arcs ≥ 135°.
On short arcs the Kasa, RANSAC and cylinder fits are biased low (DBH 40 cm, N = 200: −2.4 cm at 90°,
−7.1 cm at 67.5°), whereas the geometric fit stays unbiased (RMSE 0.8 cm at 90°); coverage thresholds
of the least-squares and RANSAC fits are 45–135° at σ ≤ 5 mm and up to 180° at σ = 10 mm, depending on
estimator and N (Fig. 1a); Hough needs 180–225°.

![**Figure 1.** Monte Carlo experiment: RMSE of DBH versus visible arc for six estimators (DBH 40 cm, 200
points, σ = 5 mm). (a) ideal circle, (b) non-circular cross-section (axis ratio 0.85–1), (c) 15 %
outliers, (d) combined perturbations. Dashed line: 2 cm; dotted line: 202.5° (3DFin sector rule).](figures/fig1_mc_rmse_vs_arc.png){width=16cm}

Non-circularity shifts the thresholds of the least-squares, RANSAC and Huber fits to 157.5–202.5° for
DBH 40 cm and to 90–135° for DBH 20 cm: a partial view of an ellipse yields a systematically wrong circle, an error
that grows with diameter (Fig. 1b). Registration offsets of 5–10 mm set an RMSE floor of 0.2–0.5 cm
at full coverage but barely change thresholds.

Table 1 summarises the coverage thresholds of all estimators and scenarios. Outliers dominate everything
else (Fig. 1c). With 5–15 % outliers, Kasa, geometric and cylinder fits
never meet the threshold, even at 360° (RMSE 1.6–8.6 cm). RANSAC meets it from 112.5–135°, the
Huber-robust fit only from 135–270° (it fails on short arcs because its Kasa starting value is already
biased), Hough from 180–247.5°. Hough tolerates outliers but not non-circularity: for DBH 40 cm it
never meets the threshold on elliptical stems (RMSE at full coverage 4.7 cm with 200 points, 2.0 cm with
1000), and below 135° it fails in 29–100 % of cases. In the combined scenario only RANSAC (135–180°) and the Huber fit
(180–225°) reach the threshold for both diameters; Hough only for DBH 20 cm (202.5°).

| Scenario | Kasa | Geometric | RANSAC | Cylinder | Huber | Hough |
|---|---|---|---|---|---|---|
| Ideal | 112.5–135 | 45–67.5 | 112.5–135 | 112.5–135 | 45–67.5 | 180–225 |
| Non-circular | 135–202.5 | 90–202.5 | 135–202.5 | 135–202.5 | 90–202.5 | 202.5* |
| 5 % outliers | never | never | 112.5–135 | never | 135–270 | 180–225 |
| 15 % outliers | never | never | 112.5–135 | never | 157.5–270 | 202.5–247.5 |
| 5 mm offset | 135 | 45–67.5 | 112.5–135 | 135 | 45–67.5 | 180–202.5 |
| 10 mm offset | 135 | 45–67.5 | 112.5–135 | 135 | 45–67.5 | 180–360 |
| Combined | never | never | 135–180 | never | 180–225 | 202.5* |

**Table 1.** Coverage thresholds (°) in the Monte Carlo experiment: smallest arc from which RMSE ≤ 2 cm,
|bias| ≤ 1 cm and failure ≤ 10 % hold for all larger arcs, at σ = 5 mm. Ranges span DBH 20 and 40 cm
and N = 200 and 1000 points. "never": threshold not reached at any arc up to 360°; *: reached only
for DBH 20 cm.

### 3.2 HELIOS++: error versus visible arc

Pooled over the three stands (26 712 cases; 56, 130 and 185 core stems), the RMSE of Kasa, cylinder and
RANSAC falls from 9–17 cm below 90° to 1.6–1.7 cm at 180–225° and 0.5–0.8 cm beyond 315°; Hough remains
worst throughout (13.7 cm at 180–225°, 2.1 cm beyond 315°; Fig. 2a). The share of stems within 2 cm rises from 45–46 % at 90–135° (RANSAC 56 %) to 82 % at
180–225°, 93 % at 225–270° and 98–99 % beyond 270° for the Kasa and cylinder fits; RANSAC stays
slightly lower beyond 225° (89–94 %) (Fig. 2b). Thicker stems need more coverage:
at 180–225° RMSE is 2.0 cm in S1a (mean DBH 37 cm) versus 1.5–1.7 cm in S1b and S1c, consistent
with the non-circularity effect in the Monte Carlo experiment (Section 3.1). A single scan position sees at most 172° of a
stem (median 164°).

![**Figure 2.** HELIOS++ simulations, three stands pooled (26 712 stem × configuration cases). (a) RMSE of
DBH and (b) share of stems within ±2 cm (failures counted as outside) versus geometrically visible
arc.](figures/fig2_helios_error_vs_arc.png){width=16cm}

With the same stems and scan positions as S1b but branches crossing the breast-height band
(S1b-B), the least-squares fits collapse: at 225–270° visible arc only 11 % (Kasa), 10 %
(geometric), 9 % (cylinder) and 26 % (Huber) of stems are within 2 cm, and at most 19–43 % beyond
270°; the median error above 180° is +15 to +42 cm because branch points pull the circle outwards.
RANSAC is practically unaffected (71 %, 79 % and 89 % at 135–180°, 180–225° and 225–270°, versus
73 %, 80 % and 90 % without branches). Hough degrades (43 % instead of 70 % at 225–270°; Fig. 3).

![**Figure 3.** Effect of branches at breast height: share of stems within ±2 cm versus geometrically
visible arc in (a) stand S1b and (b) the same stand with branches crossing the 1.05–1.55 m band
(S1b-B); stem and branch points are segmented together, as after a real stem segmentation. Dotted
line: 202.5°.](figures/fig3_branches.png){width=16cm}

Table 2 lists the 80 % points for all datasets. The cluster bootstrap places the 80 % point of the Kasa, cylinder
and RANSAC fits in the 180–225° class for the pooled HELIOS stands (95 % CI: 180–225° to 225–270°),
of the geometric and Huber fits one class higher, and of Hough in the 270–315° class. With branches,
RANSAC reaches 80 % in the 225–270° class (CI 180–225° to 225–270°), Hough only beyond 315°, and the
least-squares and Huber fits never.

| Dataset | Kasa | Geometric | RANSAC | Cylinder | Huber | Hough |
|---|---|---|---|---|---|---|
| HELIOS, three stands (371 stems) | 180–225 (180–225 to 225–270) | 225–270 (180–225 to 225–270) | 180–225 (180–225 to 225–270) | 180–225 (180–225 to 225–270) | 225–270 (180–225 to 225–270) | 270–315 (270–315) |
| HELIOS, branches (130 stems) | – | – | 225–270 (180–225 to 225–270) | – | – | 315–360 (315–360) |
| SegmentedForests, stem points (458 stems) | 225 (225–270) | 270 (270–315) | 315 (315) | 270 (270) | 315 (270–315) | – |
| SegmentedForests, with surroundings (458 stems) | – | – | 360 (315–360) | – | – | – |
| LAUT, field DBH (460 trees) | – | – | – | – | – | – |

**Table 2.** Smallest visible arc (°) from which at least 80 % of the stems are within ±2 cm, with 95 %
cluster-bootstrap confidence interval in brackets. HELIOS values are classes of geometrically visible
arc; real-data values are retained arcs. "–": 80 % not reached at any arc.

### 3.3 Stem diameter, distance and point density

In the pooled HELIOS stands (371 core stems: 78 below 20 cm DBH, 164 of 20–30 cm, 93 of 30–40 cm and
36 of 40 cm or more), larger stems needed more visible arc for the same accuracy. At 180–225°, 89 % of
the stems below 20 cm were within 2 cm with the Kasa fit, compared with 85 %, 75 % and 70 % in the three
larger classes, and the RMSE rose from 1.2 cm to 1.6, 1.8 and 2.3 cm. At 225–270° the shares were
94 %, 96 %, 91 % and 80 %, and beyond 270° all classes reached at least 93 %. The dependence on diameter
follows from the non-circularity of the simulated cross-sections: the same relative deviation from a
circle produces a larger absolute error on a thick stem, as in the Monte Carlo experiment (Section 3.1), where
non-circularity raised the thresholds for 40 cm stems far more than for 20 cm stems (Table 1).

The visible arc decreased with the distance between a stem and the nearest scan position of a
configuration: its median was 284° for stems closer than 5 m, 259° at 5–10 m, 210° at 10–15 m and 168°
beyond 15 m. The number of points in the 10 cm slice at breast height fell even more steeply, from a
median of 1 903 to 604, 215 and 51 points. At a given visible arc, however, accuracy hardly depended on
distance or point count. At 180–225°, 87 %, 83 %, 81 % and 79 % of the stems were within 2 cm in the
four distance classes, and the share varied only between 80 % and 83 % across point counts from fewer
than 50 to more than 500. Once a few dozen points are available, the error is therefore controlled by
the visible arc rather than by point density or range.

### 3.4 Sector rule and scan design

The 3DFin rule of ≥ 9/16 sectors corresponds to a median geometric arc of 190° at exactly nine sectors
(Fig. 4); 7.2 % of accepted stems have less than 180° visible. Used as an acceptance filter, the rule
separates stems with 92 % (Kasa) of estimates within 2 cm from those with 53 % — it sits close to the
arc at which errors become small in these simulations.

![**Figure 4.** Occupied 22.5° sectors (3DFin rule) versus geometrically visible arc in the HELIOS++
simulations; boxes show quartiles, whiskers 1.5 IQR. Dashed lines: 202.5° sector rule and 180°
visible arc.](figures/fig4_sector_vs_geometric.png){width=16cm}

Coverage depends more on the spread than on the number of positions (Fig. 5). Four grid positions
bring 89 %, 82 % and 80 % of stems above 180° in the three stands; six bring 96–98 %. Four positions
clustered near the centre reach 89 %, 71 % and 56 %, i.e. the penalty of clustering grows with stand
density. Random placement performs close to the grid.

![**Figure 5.** Share of stems with ≥ 180° visible arc versus number of scan positions for grid, random
(mean of 10 draws) and clustered placement in stands of 400, 800 and 1200 stems ha⁻¹.](figures/fig5_design_coverage.png){width=16cm}

### 3.5 Real point clouds

The real multi-scan clouds themselves do not guarantee full coverage. Of the 1 908 LAUT trees, the
observed coverage around the fitted centre (5° classes) had a median of 265°; 82 % of the trees were
covered on at least 180° and 24 % on at least 330°, so that only about a quarter of the trees could serve
for the arc reduction.

With stem points only (SegmentedForests, Fig. 6a), the Kasa fit reaches 56 % of stems within 2 cm at
180°, 72 % at 202.5°, 82 % at 225° and 91 % at 270°; its RMSE falls from 6.1 cm at 135° to 2.9 cm at
202.5° and 1.5 cm at 270°, with a negative bias on short arcs (−4.4 cm at 135°, −1.0 cm at 202.5°)
as predicted by the Monte Carlo experiment. On these thinner stems (median DBH 16 cm), real bark
shifts the 80 % point from about 180° (HELIOS) to about 225°. RANSAC with a 12 mm inlier tolerance
is weaker on clean real stems (87 % at 360°), because rough bark excludes valid points. Hough reaches
only 58 % even at 360°.

![**Figure 6.** Real point clouds, share of stems within ±2 cm versus retained arc. (a) SegmentedForests,
stem points only (458 stems, reference: fit on full coverage); (b) the same stems with surrounding
points within 30 cm; (c) LAUT, 460 well-covered trees against field DBH, with surrounding points within
25 cm.](figures/fig6_real_data.png){width=16cm}

When branches, understorey and unlabelled points within 30 cm (SegmentedForests) or 25 cm (LAUT)
remain (Fig. 6b, c), the least-squares fits saturate: at full coverage only
55 % (Kasa) and 64 % (geometric) of SegmentedForests stems are within 2 cm, and 35–38 % of LAUT trees
against field DBH. RANSAC rises with coverage to 84 % (SegmentedForests) and 62 % (LAUT) and is the
best estimator from about 112° on, reproducing the outlier scenario of the Monte Carlo experiment (Section 3.1) on real data. The
lower LAUT values include field-measurement error and the absence of any segmentation. Bootstrap 80 % points
(95 % CI) on SegmentedForests: Kasa 225° (225–270°), cylinder 270° (270°), geometric 270° (270–315°),
RANSAC and Huber 315° (270–315° for Huber); with surrounding points only RANSAC at 360° (315–360°);
on LAUT no estimator reaches 80 % at any arc.

### 3.6 3DFin on real plots with reduced coverage

The full-cloud runs gave 296 reference stems in 12 plots (median DBH 23.6 cm). Under reduced coverage
3DFin still detects most stems (66 % with one position, 83–96 % with two to six), but accepts a DBH for
far fewer: 10 % with one position, 24 %, 36 %, 49 % and 54 % with two, three, four and six spread
positions, and 36 % with four clustered positions, which behave like three spread ones (Fig. 7). The
median visible arc of the reference stems was 166° with one position, 168° with two, 209° with three,
247° with four and 283° with six spread positions, and the share of stems with at least 180° rose from
0 % to 43 %, 68 %, 80 % and 93 %; four clustered positions gave a median of 193° and 75 % of stems above
180°. By
visible arc, acceptance rises from 16 % at 135–180° and 36 % at 180–225° to 52–56 % at 225–315° and
76 % beyond 315°. The accepted diameters are accurate: 88 % lie within 2 cm of the full-coverage value
(66 % at 135–180°, 78 % at 180–225°, 95 % at 225–270°, ≥ 96 % beyond), and 14 % of the accepted
diameters come from stems with less than 180° visible. On real plots the sector rule thus acts as
intended — it filters poorly covered stems — but at the price of completeness: with four spread
positions half of the reference stems receive no DBH.

![**Figure 7.** 3DFin on twelve SegmentedForests plots with simulated reduced coverage (1–6 virtual scan
positions): share of the 296 reference stems detected and with an accepted DBH, and share of accepted
diameters within ±2 cm of the full-coverage 3DFin value, by geometrically visible arc (classes with
fewer than ten accepted diameters omitted). Dotted line: 202.5°.](figures/fig7_3dfin_real.png){width=16cm}

## 4. Discussion

The coverage needed for a reliable DBH is not a single number. Under ideal conditions least-squares
circle fits reached an RMSE of 2 cm with less than half of the circumference visible, whereas
non-circular cross-sections raised the requirement to 160–200° for 40 cm stems, and outliers prevented
least-squares fits from reaching it at any coverage (Fig. 1). The threshold is therefore a property of
the estimator and of the expected cross-section rather than of the point cloud alone. For least-squares
fits of clean stem points, the simulations confirm the guideline of Li et al. (2021) that a CDRC of
about 200° is required: 82 % of the simulated stems were within 2 cm at 180–225° of visible arc. On real
stems with rough bark and a median DBH of 16 cm, however, the 80 % point shifted to 225°, with a
bootstrap interval reaching 270°. The negative bias of the Kasa fit on short real arcs (−4.4 cm at 135°,
−1.0 cm at 202.5°) matches the short-arc bias of algebraic fits in the Monte Carlo experiment (Section 3.1) and is in
line with the negative DBH bias that Bauwens et al. (2016) found for all scanning approaches and
attributed to bark roughness and non-circular cross-sections.

The required coverage also grows with stem diameter. In the simulated stands, stems of 40 cm or more
reached the 80 % level only beyond 270°, whereas stems below 20 cm reached it at 135–180° (Section
3.3). A rule expressed as a fixed angle is therefore stricter than necessary
for thin stems and too lenient for thick ones, at least where cross-sections deviate from a circle. In
absolute terms the effect is plausible: the same relative non-circularity displaces the fitted circle by
more centimetres on a thick stem. Inventories that emphasise large trees, for example for volume or
biomass, should therefore aim at more coverage than a single angular rule suggests, or use estimators
that model the cross-section shape.

Segmentation proved more decisive than coverage. When branch points entered the breast-height band in
the simulation (Fig. 3), or when the surrounding points were left in the real data (Fig. 6b, c),
least-squares fits failed at any coverage, because a few points outside the stem surface pull the
fitted circle outwards. RANSAC with an arc constraint kept its accuracy under the same conditions, so
that the outlier scenarios of the Monte Carlo experiment were reproduced in simulated and real stands.
This agrees with earlier findings that the circle-fitting method affects diameter estimates from TLS
(Pueschel et al., 2013) and that RANSAC reduces the influence of noise (Olofsson et al., 2014). The price
of robustness was a lower ceiling on clean real stems, where the 12 mm inlier tolerance excluded valid
points on rough bark (87 % within 2 cm at full coverage). A coverage rule is therefore meaningful only
together with a statement of how stem points were separated from branches and understorey and which
estimator was applied to them.

The simulations also separate two quantities that are usually confounded in field data: the visible
arc and the point density. Both decrease with distance from the scanner, and Olofsson et al. (2014)
reported that the proportion of detected trees decreased with distance following the decrease of
visible area. For the diameter error, the present results point to the arc as the controlling factor.
At a given visible arc, the share of stems within 2 cm changed by only a few percentage points between
stems closer than 5 m and stems beyond 15 m, and between fewer than 50 and more than 500 points in the
breast-height slice, whereas it changed by tens of percentage points between arc classes. Point density
matters for detection and for the stability of the fit on very sparse stems, but once a few dozen
points describe the visible arc, adding points does not compensate for missing circumference. Scan
planning should therefore target the angular coverage of stems rather than point density alone.

On real plots, the sector rule of 3DFin acted as intended. Accepted diameters were within 2 cm of the
full-coverage value for 78 % of the stems at 180–225° and 95 % at 225–270°, close to the behaviour of
least-squares fits in the simulations, and in the simulated stands the rule separated stems with 92 %
from those with 53 % of estimates within 2 cm. With a median of 190° geometric arc at exactly nine
occupied sectors, the rule sits close to the coverage at which errors become small. The cost is
completeness: with four or six spread positions about half of the reference stems received no
diameter, and a quarter of the stems with more than 315° visible were still rejected. Unless the
rejected stems are measured otherwise or imputed, inventories that rely on such rules should report the
share of stems without DBH, and scan designs should aim at more coverage than the nominal 202.5°.

The accuracies obtained here are of the same order as those reported for ground-based laser scanning.
For hand-held mobile scanning, Bauwens et al. (2016) found a DBH bias of −0.08 cm and an RMSE of 1.11 cm,
with the full cross-section scanned for 91 % of the trees, and Ryding et al. (2015) an RMSE of 1.5 cm
relative to a concurrent TLS survey. With an early personal laser scanning system the RMSE was 5.06 cm
(Liang et al., 2014), and for TLS plots Olofsson et al. (2014) reported a relative RMSE of 14 % within
10 m of the scanner. The simulated RMSE of 1.6–1.7 cm at 180–225° and 0.5–0.8 cm beyond 315° is at the
favourable end of this range, as expected for perfect segmentation and modest bark roughness; the real
SegmentedForests stems, with an RMSE of 2.9 cm at 202.5° and 1.5 cm at 270° for the Kasa fit, are closer
to field conditions. The comparison supports the interpretation that much of the spread between studies
reflects how much of each stem was seen and how stem points were isolated, not only the sensor.

Spreading scan positions mattered more than adding them. Four grid positions brought 80–89 % of the
simulated stems above 180° of visible arc, whereas four positions clustered near the plot centre reached
only 56 % in the densest stand, about as many as three grid positions (58 %); six grid positions brought
96–98 % of the stems above 180°. This agrees with Abegg et al. (2017), who found evenly distributed scan
positions to give the best visibility, and with the use of regular scan grids for plot-scale structural
modelling (Wilkes et al., 2017). A single position never saw more than 172° of a stem in the
simulations, so single-scan TLS cannot meet a 180–200° criterion for any stem, consistent with the
absence of fully scanned trees in single-scan data reported by Bauwens et al. (2016). As a tentative
recommendation for stands of 400–1200 stems ha⁻¹, a spread grid of four to six positions per 0.16 ha
(25–38 positions per hectare) brought 80–98 % of the stems above 180°; stand-specific simulation can
refine this.

It may be argued that occlusion becomes less relevant as mobile and personal laser scanning improve and
as static scanners become faster. Hand-held scanning recorded the full cross-section of most trees in
one comparison (Bauwens et al., 2016), and PLS detected more trees than TLS on inventory plots (Gollob et
al., 2020c). Faster static scanners allow more positions per plot, and the present results show that the
benefit of additional positions depends strongly on their arrangement. The coverage question does not
disappear with mobile systems, however. Their coverage is governed by the trajectory instead of fixed
positions, and the density of walking lines affected single-tree estimates from hand-held scanning
(Del Perugia et al., 2019). Kuželka (2025) used simulation to design hand-held trajectories in complex
natural forests and found that occlusion reduced stem point density and detection and increased DBH
errors. The present study is complementary: it addresses static scan positions, the choice of estimator
and the acceptance rules of processing software, and expresses coverage as a geometric visible arc that
can equally be computed along a trajectory. Mobile workflows also fit stems from partial arcs; one workflow, for
example, detects stem arcs and matches them iteratively to cope with drift of the simultaneous localization and mapping (SLAM) trajectory
(Hyyppä et al., 2020). The visible arc used here describes the geometry between sensor and stem, not the
sensor type, so the thresholds apply to any ground-based point cloud once the recorded arc of each stem
is known. Static TLS also remains in use where its accuracy and repeatability are needed, including
tests in national forest inventories (Holvoet et al., 2025).

Several practical recommendations follow. First, the estimator should be chosen with the segmentation
in mind: least-squares fits are adequate, and on short arcs the geometric fit preferable, only for
clean stem points, whereas point sets that may contain branches or understorey call for a robust,
arc-constrained estimator such as RANSAC. Second, coverage should be planned and reported as the visible
arc per stem, which can be estimated from stem positions and scan positions before or after scanning,
rather than as point density or number of positions. Third, for least-squares fits of well-segmented
stems, about 200–225° of visible arc should be the target, more for thick or irregular stems. Fourth,
scan positions should be spread over the plot; in the simulated stands, four to six positions on a grid
brought most stems above 180°, while clustering near the centre lost a large part of that benefit in
dense stands. Fifth, inventories that apply acceptance rules should report the share of rejected
stems, because the accepted diameters alone can give a misleading impression of completeness.

Several limitations apply. In the HELIOS++ scenes, segmentation was perfect, crowns were absent,
branches were represented in one scene only and as simple cylinders, the terrain was flat, a single
scanner model was used, and outliers and registration offsets were idealised; range-dependent incidence
effects and beam divergence were simulated but not varied systematically. Mobile trajectories were not
simulated. Hough was run with scikit-image defaults; other accumulator normalisations or smoothing may
behave differently, but no parameter was tuned for any estimator. On SegmentedForests the reference DBH
is itself a fit to well-covered points, not a field measurement, and the 3DFin experiment simulated
reduced coverage by removing points from a multi-scan cloud with a stem-only occlusion model; real
single-position scans differ in point density and range effects, and the reference there is the
full-coverage result of 3DFin itself.

Future work should extend the geometric analysis to mobile trajectories, so that walking or flight
paths can be planned with the same coverage targets, and to scenes with crowns, sloped terrain and
realistic branch and understorey structure. Field campaigns with measured stem perimeters and recorded
scan positions would allow the visible-arc thresholds to be tested directly against tape measurements.

## 5. Conclusions

This study quantified how the error of DBH estimates from ground-based laser scanning depends on the
visible part of the stem circumference, using controlled simulations, virtual laser scanning and open
real data. Coverage rules for TLS diameters should be reported per estimator and per segmentation quality.
With clean stem points, least-squares fits need about 180° (simulation) to 225° (real bark) of
visible arc for most stems to be within 2 cm, and 3DFin's 202.5° sector rule sits in this range.
Without clean segmentation, no amount of coverage rescues least-squares fits; robust estimators such
as RANSAC with an arc constraint are then the main lever. Scan positions should be spread rather than
clustered, especially in dense stands. Coverage rules such as 3DFin's keep the accepted diameters accurate
but leave many stems without a DBH; the share of rejected stems belongs in every TLS inventory report.
Because the error is controlled by the visible arc rather than by point density, and because thick stems
need more coverage than thin ones, scan planning for TLS as well as for mobile systems should be based
on the expected visible arc of the stems that matter most for the inventory.

## CRediT authorship contribution statement

**Angel Naya:** Conceptualization, Methodology, Software, Formal analysis, Investigation, Data curation, Visualization, Writing – original draft, Writing – review & editing.

## Declaration of competing interest

The author declares no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work the author used Claude (Anthropic) in order to assist with programming, data analysis and drafting of the text. After using this tool, the author reviewed and edited the content as needed and takes full responsibility for the content of the published article.

## Data availability

All result tables underlying the figures and numbers are included in the Zenodo archive (Naya, 2026); simulated scenes are reproducible from the scripts and seeds. The real point clouds are third-party open data and are not redistributed: SegmentedForests (Laino et al., 2026; MIT), LAUT (Gollob et al., 2020b; CC BY 4.0). All scripts used for this study (Monte Carlo, HELIOS++ scenes and evaluation, real-data analyses, 3DFin experiment, bootstrap and figures) are archived on Zenodo (https://doi.org/10.5281/zenodo.23911186; GPL-3.0-or-later). Third-party software: HELIOS++ 2.2.2 (conda-forge), 3DFin 0.6.0 with dendromatics 0.7.0, scikit-image 0.26, NumPy, SciPy, pandas.

## Funding

This research did not receive any specific grant from funding agencies in the public, commercial, or not-for-profit sectors.

## Acknowledgements

The author thanks the creators of the open datasets SegmentedForests and LAUT for publishing their data under open licences, and the developers of
HELIOS++, 3DFin and scikit-image.

## References

- Abegg, M., Kükenbrink, D., Zell, J., Schaepman, M.E., Morsdorf, F., 2017. Terrestrial laser scanning for forest
  inventories—tree diameter distribution and scanner location impact on occlusion. Forests 8 (6), 184.
  https://doi.org/10.3390/f8060184
- Al-Sharadqah, A., Chernov, N., 2009. Error analysis for circle fitting algorithms. Electronic Journal of
  Statistics 3, 886–911. https://doi.org/10.1214/09-EJS419
- Balenović, I., Liang, X., Jurjević, L., Hyyppä, J., Seletković, A., Kukko, A., 2021. Hand-held personal laser
  scanning: current status and perspectives for forest inventory application. Croatian Journal of Forest
  Engineering 42 (1), 165–183. https://doi.org/10.5552/crojfe.2021.858
- Bauwens, S., Bartholomeus, H., Calders, K., Lejeune, P., 2016. Forest inventory with terrestrial LiDAR: a comparison
  of static and hand-held mobile laser scanning. Forests 7 (6), 127. https://doi.org/10.3390/f7060127
- Bienert, A., Georgi, L., Kunz, M., Maas, H.-G., von Oheimb, G., 2018. Comparison and combination of mobile and
  terrestrial laser scanning for natural forest inventories. Forests 9 (7), 395. https://doi.org/10.3390/f9070395
- Calders, K., Adams, J., Armston, J., Bartholomeus, H., Bauwens, S., Bentley, L.P., et al., 2020. Terrestrial laser
  scanning in forest ecology: expanding the horizon. Remote Sensing of Environment 251, 112102.
  https://doi.org/10.1016/j.rse.2020.112102
- Chernov, N., 2010. Circular and Linear Regression: Fitting Circles and Lines by Least Squares. CRC Press.
- Del Perugia, B., Giannetti, F., Chirici, G., Travaglini, D., 2019. Influence of scan density on the estimation of
  single-tree attributes by hand-held mobile laser scanning. Forests 10 (3), 277. https://doi.org/10.3390/f10030277
- Fischler, M.A., Bolles, R.C., 1981. Random sample consensus: a paradigm for model fitting with applications to
  image analysis and automated cartography. Communications of the ACM 24 (6), 381–395.
- Gollob, C., Ritter, T., Nothdurft, A., 2020a. Comparison of 3D point clouds obtained by terrestrial laser
  scanning and personal laser scanning on forest inventory sample plots. Data 5 (4), 103.
  https://doi.org/10.3390/data5040103
- [dataset] Gollob, C., Ritter, T., Nothdurft, A., 2020b. LAUT – Terrestrial and personal laser scanner data from Austrian
  forest inventory plots. Zenodo. https://doi.org/10.5281/zenodo.3698956
- Gollob, C., Ritter, T., Nothdurft, A., 2020c. Forest inventory with long range and high-speed personal laser
  scanning (PLS) and simultaneous localization and mapping (SLAM) technology. Remote Sensing 12 (9), 1509.
  https://doi.org/10.3390/rs12091509
- Gollob, C., Ritter, T., Wassermann, C., Nothdurft, A., 2019. Influence of scanner position and plot size on the
  accuracy of tree detection and diameter estimation using terrestrial laser scanning on forest inventory
  plots. Remote Sensing 11 (13), 1602. https://doi.org/10.3390/rs11131602
- Holvoet, J., Eichhorn, M.P., Giannetti, F., Kükenbrink, D., Liang, X., Mokroš, M., et al., 2025. Terrestrial and
  mobile laser scanning for national forest inventories: from theory to implementation. Remote Sensing of
  Environment 329, 114947. https://doi.org/10.1016/j.rse.2025.114947
- Hyyppä, E., Yu, X., Kaartinen, H., Hakala, T., Kukko, A., Vastaranta, M., Hyyppä, J., 2020. Comparison of backpack,
  handheld, under-canopy UAV, and above-canopy UAV laser scanning for field reference data collection in
  boreal forests. Remote Sensing 12 (20), 3327. https://doi.org/10.3390/rs12203327
- Kuželka, K., 2025. Trajectory design for handheld mobile laser scanning in complex natural forests: a
  simulation approach. ISPRS Journal of Photogrammetry and Remote Sensing 230, 524–546.
  https://doi.org/10.1016/j.isprsjprs.2025.09.025
- Kåsa, I., 1976. A circle fitting procedure and its error analysis. IEEE Transactions on Instrumentation and
  Measurement IM-25 (1), 8–14. https://doi.org/10.1109/TIM.1976.6312298
- Laino, D., Cabo, C., Ordóñez, C., Bolanos, R., Janvier, R., Giulioni, F., Herrmann, M., Hudak, A., Parsons, R.,
  Santín, C., 2026. SegmentedForests: a labelled dataset of terrestrial LiDAR point clouds for semantic
  segmentation of forests. Forestry 99 (2). https://doi.org/10.1093/forestry/cpaf062
- Laino, D., Cabo, C., Prendes, C., Janvier, R., Ordóñez, C., Nikonovas, T., Doerr, S., Santín, C., 2024. 3DFin:
  a software for automated 3D forest inventories from terrestrial point clouds. Forestry 97 (4), 479–496.
  https://doi.org/10.1093/forestry/cpae020
- Li, L., Mu, X., Soma, M., Wan, P., Qi, J., Hu, R., Zhang, W., Tong, Y., Yan, G., 2021. An iterative-mode scan
  design of terrestrial laser scanning in forests for minimizing occlusion effects. IEEE Transactions on
  Geoscience and Remote Sensing 59 (4), 3547–3566. https://doi.org/10.1109/TGRS.2020.3018643
- Liang, X., Hyyppä, J., Kaartinen, H., et al., 2018. International benchmarking of terrestrial laser scanning
  approaches for forest inventories. ISPRS Journal of Photogrammetry and Remote Sensing 144, 137–179.
  https://doi.org/10.1016/j.isprsjprs.2018.06.021
- Liang, X., Kankare, V., Hyyppä, J., Wang, Y., Kukko, A., Haggrén, H., et al., 2016. Terrestrial laser scanning in
  forest inventories. ISPRS Journal of Photogrammetry and Remote Sensing 115, 63–77.
  https://doi.org/10.1016/j.isprsjprs.2016.01.006
- Liang, X., Kukko, A., Kaartinen, H., Hyyppä, J., Yu, X., Jaakkola, A., Wang, Y., 2014. Possibilities of a personal
  laser scanning system for forest mapping and ecosystem services. Sensors 14 (1), 1228–1248.
  https://doi.org/10.3390/s140101228
- Mokroš, M., Mikita, T., Singh, A., Tomaštík, J., Chudá, J., Wężyk, P., et al., 2021. Novel low-cost mobile mapping
  systems for forest inventories as terrestrial laser scanning alternatives. International Journal of Applied
  Earth Observation and Geoinformation 104, 102512. https://doi.org/10.1016/j.jag.2021.102512
- Molina-Valero, J.A., Martínez-Calvo, A., Ginzo Villamayor, M.J., Novo Pérez, M.A., Álvarez-González, J.G.,
  Montes, F., Pérez-Cruzado, C., 2022. Operationalizing the use of TLS in forest inventories: the R package
  FORTLS. Environmental Modelling & Software 150, 105337. https://doi.org/10.1016/j.envsoft.2022.105337
- [dataset] Naya, A., 2026. Code and results for: "How much of the stem must a terrestrial laser scanner see?" Zenodo, v1. https://doi.org/10.5281/zenodo.23911186
- Olofsson, K., Holmgren, J., Olsson, H., 2014. Tree stem and height measurements using terrestrial laser scanning
  and the RANSAC algorithm. Remote Sensing 6 (5), 4323–4344. https://doi.org/10.3390/rs6054323
- Pueschel, P., Newnham, G., Rock, G., Udelhoven, T., Werner, W., Hill, J., 2013. The influence of scan mode and
  circle fitting on tree stem detection, stem diameter and volume extraction from terrestrial laser scans.
  ISPRS Journal of Photogrammetry and Remote Sensing 77, 44–56. https://doi.org/10.1016/j.isprsjprs.2012.12.001
- Ritter, T., Gollob, C., Nothdurft, A., 2020. Towards an optimization of sample plot size and scanner position
  layout for terrestrial laser scanning in multi-scan mode. Forests 11 (10), 1099. https://doi.org/10.3390/f11101099
- Ryding, J., Williams, E., Smith, M.J., Eichhorn, M.P., 2015. Assessing handheld mobile laser scanners for forest
  surveys. Remote Sensing 7 (1), 1095–1111. https://doi.org/10.3390/rs70101095
- Wilkes, P., Lau, A., Disney, M., Calders, K., Burt, A., Gonzalez de Tanago, J., et al., 2017. Data acquisition
  considerations for terrestrial laser scanning of forest plots. Remote Sensing of Environment 196, 140–153.
  https://doi.org/10.1016/j.rse.2017.04.030
- Winiwarter, L., Esmorís Pena, A.M., Weiser, H., Anders, K., Martínez Sánchez, J., Searle, M., Höfle, B., 2022.
  Virtual laser scanning with HELIOS++: a novel take on ray tracing-based simulation of topographic
  full-waveform 3D laser scanning. Remote Sensing of Environment 269, 112772. https://doi.org/10.1016/j.rse.2021.112772
- van der Walt, S., Schönberger, J.L., Nunez-Iglesias, J., Boulogne, F., Warner, J.D., Yager, N., Gouillart, E.,
  Yu, T., the scikit-image contributors, 2014. scikit-image: image processing in Python. PeerJ 2, e453.
  https://doi.org/10.7717/peerj.453
