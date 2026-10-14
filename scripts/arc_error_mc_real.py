#!/usr/bin/env python3
"""arc_error_mc_real.py -- BHD-Fehler vs. Bogen unter realen Stoerungen (Paper C).

Erweitert arc_error_mc.py (idealer Kreis + Gauss-Rauschen) um die drei Effekte,
die eine strenge Abdeckungsregel wie 3DFins 202,5 Grad in der Praxis rechtfertigen
koennten:

  unrund    elliptischer Querschnitt, Achsverhaeltnis U(0.85, 1.0), zufaellig gedreht.
            Wahrer BHD = Umfang/pi (Massband-Definition, Ramanujan-Naeherung).
  ausr5/15  5 bzw. 15 % Ausreisser: Punkte vor dem Stamm (Zweige, Laub, Unterwuchs),
            radial 2-30 cm ausserhalb der Mantelflaeche auf dem sichtbaren Bogen.
  vers5/10  Registrierversatz zwischen zwei Scans: die zweite Haelfte des Bogens
            stammt aus einem anderen Standpunkt und ist um 5 bzw. 10 mm verschoben
            (Doppelwand). Gilt nur fuer Boegen > 90 Grad (darunter ein Scan).
  komb      unrund + ausr5 + vers5.

Verfahren: die vier aus dbh_methods.py plus
  hough     Kreis-Hough nach scikit-image (hough_circle, normalisiert), 5-mm-Raster
  robust    geometrischer Kreisfit mit Huber-Verlust (f_scale 1 cm)

  python scripts/arc_error_mc_real.py --out Paper_ODT/Forst_Benchmark_Paper/results/arc_error_mc_real.csv
"""
import argparse
import csv
import math
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import dbh_methods as dm                                   # noqa: E402
from arc_error_mc import crlb_radius, sectors16            # noqa: E402

ARCS = [45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 315, 360]
SCENARIOS = ["ideal", "unrund", "ausr5", "ausr15", "vers5", "vers10", "komb"]
NPTS = [200, 1000]
DBHS_CM = [20, 40]
SIGMA_MM = 5
METHODS = ["kreisfit", "geofit", "ransac", "zylinder", "hough", "robust"]


# ------------------------------------------------------------------ Stoerungen
def ellipse_perimeter(a, b):
    h = ((a - b) / (a + b)) ** 2
    return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))


def sample(rng, scen, r, theta, n, sigma):
    """Punkte (n x 3) und wahrer BHD in cm fuer ein Szenario."""
    unr = scen in ("unrund", "komb")
    out_frac = {"ausr5": .05, "ausr15": .15, "komb": .05}.get(scen, 0.0)
    shift = {"vers5": .005, "vers10": .010, "komb": .005}.get(scen, 0.0)

    if unr:
        q = rng.uniform(.85, 1.0)
        a = r * 2 / (1 + q); b = a * q             # mittlerer Radius ~ r
        rot = rng.uniform(0, math.pi)
        true_dbh = 100 * ellipse_perimeter(a, b) / math.pi
    else:
        a = b = r; rot = 0.0
        true_dbh = 200 * r

    start = rng.uniform(0, 2 * math.pi)
    t = np.radians(rng.uniform(-theta / 2, theta / 2, n))
    phi = start + t
    # Punkt auf der Ellipse in Richtung phi (Polarform)
    ang = phi - rot
    rad = a * b / np.sqrt((b * np.cos(ang)) ** 2 + (a * np.sin(ang)) ** 2)
    rad = rad + rng.normal(0, sigma, n)
    if out_frac:
        k = rng.random(n) < out_frac
        rad[k] += rng.uniform(.02, .30, k.sum())
    x, y = rad * np.cos(phi), rad * np.sin(phi)
    if shift and theta > 90:
        k = t > 0                                  # zweite Bogenhaelfte = zweiter Scan
        d = rng.uniform(0, 2 * math.pi)
        x[k] += shift * math.cos(d); y[k] += shift * math.sin(d)
    z = rng.uniform(1.0, 1.6, n)
    return np.stack([x, y, z], axis=1), true_dbh


# ------------------------------------------------------------------ Verfahren
def m_hough(sl):
    """Kreis-Hough nach scikit-image (hough_circle / hough_circle_peaks, normalisierte
    Akkumulatoren), zweistufig: grob auf 1-cm-Raster ueber alle Radien R_MIN..R_MAX
    (Akkumulator ueber den Bildrand hinaus, da das Zentrum bei kurzen Boegen ausserhalb
    der Punkte liegt), dann fein auf 2,5-mm-Raster um den groben Kreis (+/- 1,5 cm).
    Etablierte Standardimplementierung statt eigener Variante."""
    if len(sl) < 12:
        return None
    from skimage.transform import hough_circle, hough_circle_peaks
    p = sl[:, :2]

    def raster(px, lo, size):
        ij = np.floor((p - lo) / px).astype(int)
        ok = (ij >= 0).all(1) & (ij < size).all(1)
        img = np.zeros((size, size), bool); img[ij[ok, 0], ij[ok, 1]] = True
        return img

    # grob
    px = .01
    lo = p.min(axis=0) - .02
    size = int(np.ptp(p, axis=0).max() / px) + 5
    if size > 300:
        return None
    radii = np.arange(int(dm.R_MIN / px), int(dm.R_MAX / px) + 1)
    acc = hough_circle(raster(px, lo, size), radii, normalize=True, full_output=True)
    _, cx, cy, rr = hough_circle_peaks(acc, radii, total_num_peaks=1)
    if not len(rr):
        return None
    pad = radii.max()
    c0 = lo + (np.array([cx[0], cy[0]]) - pad + .5) * px
    r0 = float(rr[0]) * px
    # fein
    px = .0025
    half = r0 + .03
    lo = c0 - half
    size = int(2 * half / px) + 1
    radii = np.arange(max(int(dm.R_MIN / px), int((r0 - .015) / px)), int(min(dm.R_MAX, r0 + .015) / px) + 1)
    acc = hough_circle(raster(px, lo, size), radii, normalize=True)
    _, cx, cy, rr = hough_circle_peaks(acc, radii, total_num_peaks=1)
    if not len(rr):
        return None
    r = float(rr[0]) * px
    if r <= dm.R_MIN + 1e-4 or r >= dm.R_MAX - 1e-4:
        return None
    return round(200 * r, 1)


def m_robust(sl, f_scale=.01):
    """Geometrischer Kreisfit mit Huber-Verlust; Start aus Kasa, beschraenkt wie geofit."""
    if len(sl) < 12:
        return None
    from scipy.optimize import least_squares
    px, py = sl[:, 0], sl[:, 1]
    st = dm.fit_circle(px, py)
    if st is None:
        return None
    cx0, cy0, r0 = st[0], st[1], min(max(st[2], dm.R_MIN), dm.R_MAX)
    lo = [cx0 - .3, cy0 - .3, dm.R_MIN]; hi = [cx0 + .3, cy0 + .3, dm.R_MAX]
    try:
        res = least_squares(lambda q: np.hypot(px - q[0], py - q[1]) - q[2], [cx0, cy0, r0],
                            bounds=(lo, hi), loss="huber", f_scale=f_scale, max_nfev=300)
    except Exception:
        return None
    r = float(res.x[2])
    if abs(r - dm.R_MIN) < 1e-4 or abs(r - dm.R_MAX) < 1e-4:
        return None
    return round(200 * r, 1)


def run_cell(args):
    scen, theta, n, dbh_cm, reps, seed = args
    rng = np.random.default_rng(seed)
    r, sigma = dbh_cm / 200.0, SIGMA_MM / 1000.0
    err = {m: [] for m in METHODS}
    fail = {m: 0 for m in METHODS}
    acc = 0
    for _ in range(reps):
        pts, true = sample(rng, scen, r, theta, n, sigma)
        acc += sectors16(pts) >= 9
        sl = pts[np.abs(pts[:, 2] - 1.3) <= .25]
        est = {"kreisfit": dm.m_kreisfit(sl)[0], "geofit": dm.m_geofit(sl), "ransac": dm.m_ransac(sl)[0],
               "zylinder": dm.m_zylinder(pts)[0], "hough": m_hough(sl), "robust": m_robust(sl)}
        for m, v in est.items():
            if v is None:
                fail[m] += 1
            else:
                err[m].append(v - true)
    crlb = round(200 * crlb_radius(theta, n, sigma), 3)
    rows = []
    for m in METHODS:
        e = np.array(err[m])
        rows.append({"scenario": scen, "method": m, "arc_deg": theta, "n_pts": n, "dbh_cm": dbh_cm,
                     "sigma_mm": SIGMA_MM, "reps": reps, "fail_rate": round(fail[m] / reps, 3),
                     "bias_cm": round(float(e.mean()), 3) if len(e) else "",
                     "rmse_cm": round(float(np.sqrt((e ** 2).mean())), 3) if len(e) else "",
                     "mae_cm": round(float(np.abs(e).mean()), 3) if len(e) else "",
                     "p90_abs_cm": round(float(np.quantile(np.abs(e), .9)), 3) if len(e) else "",
                     "crlb_sd_cm": crlb, "accept_3dfin_rule": round(acc / reps, 3)})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Paper_ODT/Forst_Benchmark_Paper/results/arc_error_mc_real.csv")
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261014)
    args = ap.parse_args()
    cells, k = [], 0
    for s in SCENARIOS:
        for th in ARCS:
            for n in NPTS:
                for d in DBHS_CM:
                    cells.append((s, th, n, d, args.reps, args.seed + k)); k += 1
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for i, rr in enumerate(ex.map(run_cell, cells), 1):
            rows += rr
            if i % 25 == 0:
                print(f"{i}/{len(cells)} Zellen", flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {len(rows)} Zeilen")


if __name__ == "__main__":
    main()
