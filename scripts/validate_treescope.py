#!/usr/bin/env python3
"""validate_treescope.py -- Inventur-Baseline gegen TreeScope-Ground-Truth pruefen.

TreeScope liefert je Punkt ein Instanz-Label (0 = Boden, -100 = ignorieren,
>=1 = Einzelbaum-ID). Damit laesst sich die geometrische Stammerkennung aus
inventory_from_cloud.py quantitativ validieren -- der im Projekt geforderte,
publikationswuerdige Schritt (Detektion gegen Referenz statt Augenschein).

Verfahren:
  1. Ground-Truth-Baumpositionen aus den Instanz-Labels (Stammfuss-Band je Baum)
  2. detektierte Staemme aus der Inventur-CSV (gleicher XY-Rahmen wie die .pcd)
  3. Greedy-Nearest-Matching innerhalb --match-dist
  4. Recall / Precision / F1 + Lagefehler der Treffer

Nutzung:
  python validate_treescope.py cloud1_0_all_points.pcd cloud1_0_all_points.labels \
      cloud1_0_trees.csv [--match-dist 0.6] [--min-gt-points 40]
"""
import argparse
import csv
import math
import sys

import numpy as np

from pcd_io import read_pcd, read_labels

IGNORE = {-100}      # TreeScope-Ignorierklasse
GROUND = {0}         # Boden / nicht Baum
BASE_LO, BASE_HI = 0.3, 1.8   # m ueber Instanz-Fuss: Stammband fuer die XY-Position


def gt_tree_positions(x, y, z, lab, min_points):
    """Referenzpositionen je Instanz-Label (Median des Stammfuss-Bands)."""
    trees = []
    for tid in np.unique(lab):
        if tid in IGNORE or tid in GROUND:
            continue
        m = lab == tid
        if int(m.sum()) < min_points:
            continue
        zx, zy, zz = x[m], y[m], z[m]
        base = np.percentile(zz, 2)
        band = (zz - base >= BASE_LO) & (zz - base <= BASE_HI)
        sx, sy = (zx[band], zy[band]) if band.sum() >= 3 else (zx, zy)
        trees.append({"id": int(tid), "x": float(np.median(sx)),
                      "y": float(np.median(sy)), "n": int(m.sum())})
    return trees


def load_detected(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [{"x": float(r["x"]), "y": float(r["y"]),
                 "BHD_cm": float(r.get("BHD_cm") or "nan"),
                 "label": r.get("label", "")} for r in csv.DictReader(f)]


def match(gt, det, max_dist):
    """Greedy: kuerzeste Paare zuerst; jeder GT/Det hoechstens einmal."""
    pairs = []
    for i, g in enumerate(gt):
        for j, d in enumerate(det):
            dist = math.hypot(g["x"] - d["x"], g["y"] - d["y"])
            if dist <= max_dist:
                pairs.append((dist, i, j))
    pairs.sort()
    gt_used, det_used, matches = set(), set(), []
    for dist, i, j in pairs:
        if i in gt_used or j in det_used:
            continue
        gt_used.add(i); det_used.add(j)
        matches.append((i, j, dist))
    return matches, gt_used, det_used


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("pcd")
    ap.add_argument("labels")
    ap.add_argument("detected", help="Inventur-CSV (inventory_from_cloud.py)")
    ap.add_argument("--match-dist", type=float, default=0.6, help="max. Lagefehler [m]")
    ap.add_argument("--min-gt-points", type=int, default=40,
                    help="Mindestpunktzahl je Referenzbaum (kleinere = Unterwuchs, raus)")
    args = ap.parse_args()

    x, y, z, _ = read_pcd(args.pcd)
    lab = read_labels(args.labels)
    if len(lab) != len(x):
        sys.exit(f"Punkt/Label-Anzahl unterschiedlich ({len(x)} vs {len(lab)})")

    gt = gt_tree_positions(x, y, z, lab, args.min_gt_points)
    det = load_detected(args.detected)
    if not gt:
        sys.exit("Keine Referenzbaeume oberhalb der Mindestpunktzahl")

    matches, gt_used, det_used = match(gt, det, args.match_dist)
    tp = len(matches)
    fn = len(gt) - tp            # verpasste Referenzbaeume
    fp = len(det) - tp           # Fehldetektionen
    recall = tp / len(gt)
    precision = tp / len(det) if det else 0.0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) else 0.0
    errs = [d for _, _, d in matches]

    print(f"Referenzbaeume (>= {args.min_gt_points} Punkte): {len(gt)}")
    print(f"Detektiert:                       {len(det)}")
    print(f"Treffer (<= {args.match_dist} m):              {tp}")
    print(f"Verpasst (FN):                    {fn}")
    print(f"Fehldetektionen (FP):             {fp}")
    print(f"Recall:    {recall:5.1%}")
    print(f"Precision: {precision:5.1%}")
    print(f"F1:        {f1:5.1%}")
    if errs:
        print(f"Lagefehler Treffer: Median {np.median(errs)*100:.1f} cm, "
              f"Mittel {np.mean(errs)*100:.1f} cm, max {np.max(errs)*100:.1f} cm")


if __name__ == "__main__":
    main()
