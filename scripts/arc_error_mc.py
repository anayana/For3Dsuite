#!/usr/bin/env python3
"""arc_error_mc.py -- BHD-Fehler als Funktion des sichtbaren Bogens (Paper C, Kern).

Kontrolliertes Monte-Carlo-Experiment OHNE Punktwolke: ein kreisrunder Stamm mit
bekanntem BHD wird nur auf einem zusammenhaengenden Bogen theta gesehen (Rest
verdeckt). Auf diesem Bogen liegen N Punkte mit radialem Rauschen sigma
(Messrauschen + Rindenrauheit). Darauf laufen die BHD-Verfahren der Suite
(dbh_methods.py) unveraendert:

  kreisfit  algebraischer Kreisfit (Kasa)
  geofit    geometrischer Kreisfit (Gauss-Newton, beschraenkt)
  ransac    RANSAC-Kreisfit (mit 90-Grad-Mindestbogen der Inlier)
  zylinder  3D-Zylinderfit ueber das 1,0-1,6-m-Band

Zusaetzlich die 3DFin-Annahmeregel (>= 9 von 16 Sektoren belegt) als Filter und
die Cramer-Rao-Schranke (CRLB) fuer den Radius: die kleinste Standardabweichung,
die ein unverzerrter Schaetzer bei diesem Bogen, N und sigma ueberhaupt erreichen
kann. Sie trennt "das Verfahren ist schlecht" von "die Daten tragen nicht mehr".

Ausgabe: CSV mit Bias, RMSE, MAE, Ausfallrate je Verfahren x Bogen x sigma x N x BHD.

  python scripts/arc_error_mc.py --out Paper_ODT/Forst_Benchmark_Paper/results/arc_error_mc.csv --reps 200 --jobs 4
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

ARCS = [45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 247.5, 270, 315, 360]
SIGMAS_MM = [2, 5, 10]
NPTS = [50, 200, 1000]
DBHS_CM = [20, 40]
METHODS = ["kreisfit", "geofit", "ransac", "zylinder"]


def crlb_radius(theta_deg, n, sigma):
    """Cramer-Rao-Schranke fuer den Radius (m) bei n gleichverteilten Punkten auf
    einem Bogen theta, radialem Gauss-Rauschen sigma. Parameter (a, b, r);
    Ableitung des Abstands Punkt-Kreis nach (a, b, r) = (-cos phi, -sin phi, -1)."""
    phi = np.radians(np.linspace(-theta_deg / 2, theta_deg / 2, n))
    g = np.stack([-np.cos(phi), -np.sin(phi), -np.ones_like(phi)], axis=1)
    J = g.T @ g / sigma**2
    try:
        return math.sqrt(np.linalg.inv(J)[2, 2])
    except np.linalg.LinAlgError:
        return float("nan")


def sample(rng, r, theta_deg, n, sigma, z_lo=1.0, z_hi=1.6):
    """n Punkte auf dem sichtbaren Bogen (zufaellige Lage des Bogens), 3D-Band."""
    start = rng.uniform(0, 2 * math.pi)
    phi = start + np.radians(rng.uniform(-theta_deg / 2, theta_deg / 2, n))
    rr = r + rng.normal(0, sigma, n)
    z = rng.uniform(z_lo, z_hi, n)
    return np.stack([rr * np.cos(phi), rr * np.sin(phi), z], axis=1)


def sectors16(pts):
    ang = np.degrees(np.arctan2(pts[:, 1], pts[:, 0]))
    return int(np.count_nonzero(np.histogram(ang, bins=16, range=(-180, 180))[0]))


def run_cell(args):
    theta, sig_mm, n, dbh_cm, reps, seed = args
    rng = np.random.default_rng(seed)
    r, sigma = dbh_cm / 200.0, sig_mm / 1000.0
    err = {m: [] for m in METHODS}
    fail = {m: 0 for m in METHODS}
    acc3dfin = 0
    for _ in range(reps):
        pts = sample(rng, r, theta, n, sigma)
        acc3dfin += sectors16(pts) >= 9
        sl = pts[np.abs(pts[:, 2] - 1.3) <= 0.25]
        est = {
            "kreisfit": dm.m_kreisfit(sl)[0],
            "geofit": dm.m_geofit(sl),
            "ransac": dm.m_ransac(sl)[0],
            "zylinder": dm.m_zylinder(pts)[0],
        }
        for m, v in est.items():
            if v is None:
                fail[m] += 1
            else:
                err[m].append(v - dbh_cm)
    rows = []
    crlb_cm = 200 * crlb_radius(theta, n, sigma)
    for m in METHODS:
        e = np.array(err[m])
        rows.append({
            "method": m, "arc_deg": theta, "sigma_mm": sig_mm, "n_pts": n, "dbh_cm": dbh_cm,
            "reps": reps, "fail_rate": round(fail[m] / reps, 3),
            "bias_cm": round(float(e.mean()), 3) if len(e) else "",
            "rmse_cm": round(float(np.sqrt((e**2).mean())), 3) if len(e) else "",
            "mae_cm": round(float(np.abs(e).mean()), 3) if len(e) else "",
            "p90_abs_cm": round(float(np.quantile(np.abs(e), .9)), 3) if len(e) else "",
            "crlb_sd_cm": round(crlb_cm, 3),
            "accept_3dfin_rule": round(acc3dfin / reps, 3),
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="Paper_ODT/Forst_Benchmark_Paper/results/arc_error_mc.csv")
    ap.add_argument("--reps", type=int, default=200)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20261013)
    args = ap.parse_args()

    cells, k = [], 0
    for theta in ARCS:
        for s in SIGMAS_MM:
            for n in NPTS:
                for d in DBHS_CM:
                    cells.append((theta, s, n, d, args.reps, args.seed + k)); k += 1
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with ProcessPoolExecutor(args.jobs) as ex:
        for i, rr in enumerate(ex.map(run_cell, cells), 1):
            rows += rr
            if i % 20 == 0:
                print(f"{i}/{len(cells)} Zellen", flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {len(rows)} Zeilen")


if __name__ == "__main__":
    main()
