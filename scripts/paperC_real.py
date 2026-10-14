#!/usr/bin/env python3
"""paperC_real.py -- BHD-Fehler vs. Bogen an ECHTEN Stammquerschnitten (Paper C, Abschn. 3.4).

Eingabe: Brusthoehenband einer gelabelten Plotwolke (ext_band.py; SegmentedForests:
Klasse 3 = Stamm). Vorgehen:
  1. Stammpunkte (Klasse --stem-class) im Band 1,05-1,55 m ueber Grund nach XY clustern.
  2. Nur Staemme mit >= 330 Grad belegter Rundum-Abdeckung (1-Grad-Klassen ueber
     den Kasa-Mittelpunkt) und >= 300 Punkten gelten als Referenz; Referenz-BHD =
     Median der Verfahren auf ALLEN Punkten (es gibt keinen Feld-BHD).
  3. Abdeckung kuenstlich reduzieren: nur ein zusammenhaengender Bogen theta bleibt
     (zufaellige Lage, 10 Wiederholungen); dazu optional die NICHT-Stamm-Punkte des
     Bandes im Umkreis (Aeste, Strauch) als reale Ausreisser (--with-clutter).
  4. Verfahren wie in arc_error_mc_real.py; Fehler gegen den Referenz-BHD.

  python scripts/paperC_real.py extdata/segforests/plot_06_band.npz --out Paper_ODT/Forst_Benchmark_Paper/results/real_plot06.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import dbh_methods as dm                                   # noqa: E402
from arc_error_mc_real import m_hough, m_robust            # noqa: E402
from validate_detection_gt import cluster_xy               # noqa: E402

ARCS = [45, 67.5, 90, 112.5, 135, 157.5, 180, 202.5, 225, 270, 315, 360]
METHODS = ["kreisfit", "geofit", "ransac", "zylinder", "hough", "robust"]


def estimate(pts, methods=None):
    """BHD je Verfahren; methods = Teilmenge von METHODS (Neuberechnung einzelner Spalten)."""
    methods = methods or METHODS
    sl = pts[np.abs(pts[:, 2] - 1.3) <= .25]
    if len(sl) < 12:
        return {m: None for m in methods}
    f = {"kreisfit": lambda: dm.m_kreisfit(sl)[0], "geofit": lambda: dm.m_geofit(sl), "ransac": lambda: dm.m_ransac(sl)[0],
         "zylinder": lambda: dm.m_zylinder(pts[(pts[:, 2] >= 1.0) & (pts[:, 2] <= 1.6)])[0],
         "hough": lambda: m_hough(sl), "robust": lambda: m_robust(sl)}
    return {m: f[m]() for m in methods}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("band"); ap.add_argument("--out", required=True)
    ap.add_argument("--stem-class", type=int, default=3)
    ap.add_argument("--reps", type=int, default=10)
    ap.add_argument("--with-clutter", action="store_true")
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--methods", help="nur diese Verfahren rechnen (kommagetrennt); Referenz bleibt aus allen")
    a = ap.parse_args()
    meth = a.methods.split(",") if a.methods else METHODS
    rng = np.random.default_rng(a.seed)
    d = np.load(a.band)
    P = np.stack([d["x"], d["y"], d["hag"]], 1).astype(np.float64)
    cls = d["cls"]
    stem = P[(cls == a.stem_class) & (P[:, 2] >= 1.0) & (P[:, 2] <= 1.6)]
    other = P[(cls != a.stem_class) & (P[:, 2] >= 1.0) & (P[:, 2] <= 1.6)]
    comps = cluster_xy(stem, cell=.05, min_pts=300)
    rows, nref = [], 0
    for ci, idx in enumerate(comps):
        S = stem[idx]
        fit = dm.fit_circle(S[:, 0], S[:, 1])
        if fit is None or not (dm.R_MIN <= fit[2] <= dm.R_MAX):
            continue
        cx, cy = fit[0], fit[1]
        ang = np.degrees(np.arctan2(S[:, 1] - cy, S[:, 0] - cx))
        cov = np.count_nonzero(np.histogram(ang, bins=360, range=(-180, 180))[0])
        if cov < 330:
            continue
        full = {m: v for m, v in estimate(S).items() if v is not None}
        if len(full) < 4:
            continue
        ref = float(np.median([full[m] for m in ("kreisfit", "geofit", "ransac", "zylinder") if m in full]))
        nref += 1
        near = other[np.hypot(other[:, 0] - cx, other[:, 1] - cy) < fit[2] + .3] if a.with_clutter else other[:0]
        for th in ARCS:
            for rep in range(a.reps):
                mid = rng.uniform(-180, 180)
                dlt = (ang - mid + 180) % 360 - 180
                keep = np.abs(dlt) <= th / 2
                if a.with_clutter and len(near):
                    an = np.degrees(np.arctan2(near[:, 1] - cy, near[:, 0] - cx))
                    kn = np.abs((an - mid + 180) % 360 - 180) <= th / 2
                    X = np.vstack([S[keep], near[kn]])
                else:
                    X = S[keep]
                est = estimate(X, meth)
                row = {"stem": ci, "ref_dbh_cm": round(ref, 2), "arc_deg": th, "rep": rep, "n_pts": int(keep.sum())}
                for m in meth:
                    row[f"{m}_cm"] = "" if est[m] is None else est[m]
                rows.append(row)
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {nref} Referenzstaemme, {len(rows)} Faelle")


if __name__ == "__main__":
    main()
