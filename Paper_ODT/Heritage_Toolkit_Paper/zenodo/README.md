# Code and results for: "How close is a Gaussian splat to the survey? Geometric accuracy of 3D Gaussian Splatting against photogrammetric reference point clouds of historic buildings"

Author: Angel Naya. Licence of the code: GPL-3.0-or-later (LICENSE). Result tables: CC BY 4.0.

## Contents
- `scripts/`
  - `pellis_to_colmap.py` – published Pellis camera parameters → COLMAP model (text + binary), poses in the
    point-cloud frame, initial points sampled from the reference cloud (`--no-undistort`: images are already
    undistorted)
  - `pellis_posecheck.py` – depth-buffer check of axis convention and transform direction
  - `train_pellis_runpod.sh` – one-command pipeline on a rented GPU: unpack, convert, gsplat 1.5.3 training,
    PLY export in the reference frame, geometry evaluation; `pellis_batch.sh` / `pellis_pod.sh` run several
    buildings on one pod
  - `eval_splat_geometry.py` – splat centres vs. labelled reference cloud: accuracy (median, 95 %) and
    completeness (2/5/10 cm) per class
  - `colmap_align.py` – own COLMAP reconstruction aligned to the published camera centres (diagnostics)
  - `splat_diag.py` – per-image PSNR incl. exposure-compensated PSNR on held-out views
  - `paperB_figures.py` – figures from `results/geometry_per_class.csv`
- `tests/` – unit tests (pytest)
- `results/geometry_per_class.csv` – all geometry numbers of the paper (buildings 5_CB, 3_SS, 2_OSA)

## Third-party data (not included)
Pellis, E., Masiero, A., Betti, M., Tucci, G., Grussenmeyer, P. (2025): Images&PointClouds Cultural Heritage
Dataset, Zenodo 14626611, CC BY 4.0; article: Data in Brief 60, 111661, doi:10.1016/j.dib.2025.111661.

Software: Python 3.11–3.13, NumPy < 2, SciPy, OpenCV, plyfile, PyTorch 2.4, gsplat 1.5.3, COLMAP 3.7
(diagnostics only).
