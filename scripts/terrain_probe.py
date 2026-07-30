#!/usr/bin/env python3
"""terrain_probe.py -- Gelaenderauheit und Hangneigung einer Plot-Wolke messen.

Dient genau einem Zweck: die 3DFin-Kennzahl 'res_cloth' (Maschenweite des
Cloth-Simulation-Filters fuer das Bodenmodell) BEGRUENDET zu waehlen statt zu
raten. Die SegmentedForests-Autoren liefern ihre Konfigurationen mit und
variieren zwischen den Plots im Wesentlichen genau diesen Wert (0,45 fuer die
Wienerwald-TLS-Plots, 0,7 fuer den Plot in Kantabrien). Damit gibt es Ankerwerte
-- gesucht ist, wo ein neuer Bestand dazwischen liegt.

Gemessen wird auf dem 2. Perzentil je 1-m-Zelle (Bodenschaetzung):
  neigung_deg     mittlere Hangneigung aus der ausgleichenden Ebene
  rauheit_cm      Median |Zellboden - Median der 3x3-Nachbarschaft|; die Ebene
                  faellt dabei heraus, gemessen wird also die Rauheit UM den
                  Hang herum, nicht der Hang selbst
  luecken_pct     Anteil der Zellen ohne Bodenschaetzung (Unterwuchs/Verdeckung)

  python scripts/terrain_probe.py <wolke.npz> [<wolke2.npz> ...]
"""
import argparse
import math
from pathlib import Path

import numpy as np


def probe(path, cell=1.0, pct=2, min_pts=5):
    d = np.load(path)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    ix = np.floor(xyz[:, 0] / cell).astype(np.int64)
    iy = np.floor(xyz[:, 1] / cell).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    cells = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= min_pts:
            k = int(ks[lo])
            cells[(k // 1_000_003, k % 1_000_003)] = float(np.percentile(zs[lo:hi], pct))
    if not cells:
        return None

    # Achtung: der Schluessel k // 1_000_003 stimmt nur fuer nicht-negative iy.
    # Deshalb hier direkt aus den Rasterindizes aufbauen statt zurueckzurechnen.
    grid = {}
    for a, b, z in zip(ix, iy, xyz[:, 2]):
        grid.setdefault((int(a), int(b)), []).append(z)
    ground = {c: float(np.percentile(v, pct)) for c, v in grid.items()
              if len(v) >= min_pts}

    pts = np.array([[c[0] * cell, c[1] * cell, z] for c, z in ground.items()])
    # Ausgleichsebene -> Hangneigung
    A = np.c_[pts[:, 0], pts[:, 1], np.ones(len(pts))]
    coef, *_ = np.linalg.lstsq(A, pts[:, 2], rcond=None)
    slope = math.degrees(math.atan(math.hypot(coef[0], coef[1])))

    # Rauheit gegen die lokale 3x3-Nachbarschaft (Hang faellt heraus)
    res = []
    for (a, b), z in ground.items():
        nb = [ground[(a + dx, b + dy)]
              for dx in (-1, 0, 1) for dy in (-1, 0, 1)
              if (a + dx, b + dy) in ground and (dx, dy) != (0, 0)]
        if len(nb) >= 4:
            res.append(abs(z - float(np.median(nb))))
    rough = float(np.median(res)) if res else float("nan")

    span_x = ix.max() - ix.min() + 1
    span_y = iy.max() - iy.min() + 1
    gaps = 100.0 * (1 - len(ground) / max(span_x * span_y, 1))
    return {"punkte": len(xyz), "zellen": len(ground),
            "neigung_deg": round(slope, 1), "rauheit_cm": round(100 * rough, 1),
            "luecken_pct": round(gaps, 1)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("clouds", nargs="+")
    ap.add_argument("--cell", type=float, default=1.0)
    args = ap.parse_args()
    print(f"{'Wolke':32} {'Punkte':>12} {'Zellen':>7} {'Neigung':>8} "
          f"{'Rauheit':>8} {'Luecken':>8}")
    for c in args.clouds:
        r = probe(c, args.cell)
        if not r:
            print(f"{Path(c).stem:32} -- kein Bodenmodell")
            continue
        print(f"{Path(c).stem:32} {r['punkte']:12,} {r['zellen']:7} "
              f"{r['neigung_deg']:7.1f}° {r['rauheit_cm']:7.1f}cm {r['luecken_pct']:7.1f}%")


if __name__ == "__main__":
    main()
