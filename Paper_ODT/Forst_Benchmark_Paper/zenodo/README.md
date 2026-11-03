# Code and results for: "How much of the stem must a terrestrial laser scanner see?"

Author: Angel Naya. Licence of the code: GPL-3.0-or-later (LICENSE).
Result tables: CC BY 4.0.

## Contents
- `scripts/` – all computations:
  - Monte Carlo: `arc_error_mc.py` (ideal grid), `arc_error_mc_real.py` (perturbations, all six estimators)
  - Estimators: `dbh_methods.py` (+ `inventory_from_cloud.py`, `validate_detection_gt.py` for helpers)
  - HELIOS++ 2.2.2: `paperC_scene.py` (scenes, `--branches` for S1b-B), `paperC_run.py` + `helios_run.py` + `paperC_pack.py` (simulation), `paperC_eval.py` (evaluation)
  - Real data: `paperC_real.py` (SegmentedForests), `paperC_laut.py` (LAUT), `paperC_3dfin_real.py` (3DFin with reduced coverage)
  - `paperC_bootstrap.py`, `paperC_figures.py` (Figures 1–7 from the result tables)
  - Breast-height band extraction from the original point clouds: `ext_band.py`
- `results/` – all result tables behind the paper.

## Third-party data (not included; cite and download from the original sources)
- SegmentedForests: Laino et al. (2026), doi:10.5281/zenodo.17396681 (MIT)
- LAUT: Gollob et al. (2020), doi:10.5281/zenodo.3698956 (CC BY 4.0)
- Renon / ICOS IT-Ren: Chang et al. (2025), doi:10.5281/zenodo.17186174 (CC BY 4.0)

Software: Python 3.12/3.13, NumPy, SciPy, pandas, scikit-image 0.26, HELIOS++ 2.2.2 (conda-forge),
3DFin 0.6.0 with dendromatics 0.7.0.
