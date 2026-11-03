#!/usr/bin/env python3
"""eval_splat_geometry.py -- Gauss-Zentren eines 3DGS-Modells gegen eine Referenzwolke.

Misst je Bauteil-Label der Referenz (Pellis-Format "X Y Z R G B label Nx Ny Nz"):
  Genauigkeit    Abstand Splat-Zentrum -> naechster Referenzpunkt (Median, 95 %)
  Vollstaendigkeit  Anteil Referenzpunkte mit Splat-Zentrum innerhalb 2 / 5 / 10 cm
Splats werden nach Deckkraft gefiltert (sigmoid(opacity) >= --min-opacity) und auf
die Hülle der Referenz (+ --margin) beschnitten, damit Himmel/Hintergrund nicht zaehlt.
Ein Splat bekommt das Label seines naechsten Referenzpunkts.

Beide Eingaben muessen im selben Koordinatensystem liegen (train_pellis_runpod.sh
exportiert die PLY im System der Punktwolke).

  python scripts/eval_splat_geometry.py model.ply 1_point_cloud.txt --out result.json
"""
import argparse
import json

import numpy as np
from plyfile import PlyData
from scipy.spatial import cKDTree

THRESH = (0.02, 0.05, 0.10)


def load_reference(path, chunk=2_000_000):
    xyz, lab = [], []
    with open(path, encoding="utf-8") as fh:
        while True:
            lines = [l for _, l in zip(range(chunk), fh)]
            if not lines:
                break
            lines = [l for l in lines if l.strip() and not l.lstrip().startswith(("//", "#"))]
            if lines:
                a = np.loadtxt(lines, usecols=(0, 1, 2, 6), ndmin=2)
                xyz.append(a[:, :3])
                lab.append(np.rint(a[:, 3]).astype(np.int32))
    return np.concatenate(xyz), np.concatenate(lab)


def load_splats(path, min_opacity):
    v = PlyData.read(path)["vertex"]
    xyz = np.stack([v["x"], v["y"], v["z"]], 1).astype(np.float64)
    opa = 1.0 / (1.0 + np.exp(-np.asarray(v["opacity"], np.float64)))
    return xyz[opa >= min_opacity], len(xyz)


def stats(d):
    return {"n": int(d.size), "median_m": float(np.median(d)) if d.size else None,
            "p95_m": float(np.percentile(d, 95)) if d.size else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("ply")
    ap.add_argument("reference")
    ap.add_argument("--min-opacity", type=float, default=0.5)
    ap.add_argument("--margin", type=float, default=0.5, help="Rand um die Referenz-Huelle [m]")
    ap.add_argument("--out")
    args = ap.parse_args()

    ref, lab = load_reference(args.reference)
    spl, n_all = load_splats(args.ply, args.min_opacity)
    lo, hi = ref.min(0) - args.margin, ref.max(0) + args.margin
    spl = spl[np.all((spl >= lo) & (spl <= hi), axis=1)]
    print(f"Referenz: {len(ref):,} Punkte | Splats: {n_all:,}, davon {len(spl):,} "
          f"(Deckkraft >= {args.min_opacity}, in Huelle)")

    d_acc, idx = cKDTree(ref).query(spl, workers=-1)
    d_comp, _ = cKDTree(spl).query(ref, workers=-1, distance_upper_bound=max(THRESH) * 2)
    spl_lab = lab[idx]

    res = {"splats_total": n_all, "splats_used": int(len(spl)), "reference_points": int(len(ref)),
           "min_opacity": args.min_opacity, "per_label": {}}
    for L in ["alle"] + sorted(set(lab.tolist())):
        ma = np.ones(len(spl), bool) if L == "alle" else spl_lab == L
        mc = np.ones(len(ref), bool) if L == "alle" else lab == L
        r = {"genauigkeit": stats(d_acc[ma]),
             "vollstaendigkeit": {f"{int(t*100)}cm": float(np.mean(d_comp[mc] <= t)) for t in THRESH},
             "referenzpunkte": int(mc.sum())}
        res["per_label"][str(L)] = r
        g, v = r["genauigkeit"], r["vollstaendigkeit"]
        med = f"{g['median_m']*100:6.1f}" if g["median_m"] is not None else "     -"
        p95 = f"{g['p95_m']*100:6.1f}" if g["p95_m"] is not None else "     -"
        print(f"Label {str(L):>5}: Splats {g['n']:>9,}  Median {med} cm  95% {p95} cm | "
              f"Vollst. 2/5/10 cm: {v['2cm']:.2f} {v['5cm']:.2f} {v['10cm']:.2f} "
              f"({r['referenzpunkte']:,} Ref.)")
    if args.out:
        json.dump(res, open(args.out, "w"), indent=1)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()
