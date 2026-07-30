#!/usr/bin/env python3
"""classes_probe.py -- unbenannte Punkt-Labels aus ihrer Geometrie erschliessen.

SegmentedForests speichert das Label je Punkt im Feld 'Class' (0..15). Die
Zuordnung Zahl -> Klassenname steht WEDER im Datensatz NOCH im Aufsatz als
Tabelle; dort findet sich nur ein einziger harter Satz: "Labels 6-9 correspond to
non-vegetation structures". Raten verbietet sich -- eine falsch benannte Stammklasse
wuerde jede spaetere Validierung still entwerten.

Dieses Skript benennt deshalb nichts, sondern MISST je Klasse die Eigenschaften,
an denen sich Boden, Stamm und Krone eindeutig unterscheiden, und legt die Belege
offen. Entschieden wird danach von Hand -- mit den Zahlen daneben.

Merkmale je Klasse:
  hoehe_median      Hoehe ueber Boden [m] -- Boden ~0, Krone hoch
  anteil_bh_pct     Anteil der Klassenpunkte im Brusthoehen-Band 1,05-1,55 m
  cluster_bh        Zusammenhaengende Gruppen im Brusthoehen-Band
  radius_med_cm     Medianradius dieser Gruppen -- ein Stamm ist kompakt
  vert_ausdehnung   Median der z-Spanne je Gruppe [m] -- ein Stamm laeuft durch
  hoehe_p95

  python scripts/classes_probe.py data/segforests/plot_06_analysis.npz
"""
import argparse
import json
from pathlib import Path

import numpy as np

CELL_GROUND = 1.0
BH_LO, BH_HI = 1.05, 1.55


def height_above_ground(xyz, cell=CELL_GROUND):
    ix = np.floor(xyz[:, 0] / cell).astype(np.int64)
    iy = np.floor(xyz[:, 1] / cell).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    g = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 5:
            g[int(ks[lo])] = float(np.percentile(zs[lo:hi], 2))
    default = float(np.median(list(g.values()))) if g else float(xyz[:, 2].min())
    return xyz[:, 2] - np.array([g.get(int(k), default) for k in key], np.float32)


def clusters_xy(pts, cell=0.10, min_pts=20):
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iy = np.floor(pts[:, 1] / cell).astype(np.int64)
    cells = {}
    for i, (a, b) in enumerate(zip(ix, iy)):
        cells.setdefault((int(a), int(b)), []).append(i)
    seen, out = set(), []
    for start in cells:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in cells and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        idx = np.array([i for c in comp for i in cells[c]])
        if len(idx) >= min_pts:
            out.append(idx)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud")
    ap.add_argument("--sample", type=int, default=8_000_000,
                    help="Zufallsstichprobe der Wolke (0 = alles)")
    ap.add_argument("--out", help="Ergebnis-JSON")
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    cls = d["cls"]
    if args.sample and len(xyz) > args.sample:
        sel = np.random.default_rng(0).choice(len(xyz), args.sample, replace=False)
        xyz, cls = xyz[sel], cls[sel]
    print(f"{len(xyz):,} Punkte in der Probe")

    h = height_above_ground(xyz)
    bh = (h >= BH_LO) & (h <= BH_HI)
    rows = []
    for c in sorted(np.unique(cls)):
        m = cls == c
        n = int(m.sum())
        hc = h[m]
        in_bh = m & bh
        r = {"klasse": int(c), "punkte": n,
             "anteil_pct": round(100 * n / len(xyz), 2),
             "hoehe_median_m": round(float(np.median(hc)), 2),
             "hoehe_p95_m": round(float(np.percentile(hc, 95)), 2),
             "anteil_bh_pct": round(100 * int(in_bh.sum()) / max(n, 1), 2)}
        if in_bh.sum() >= 50:
            cl = clusters_xy(xyz[in_bh])
            r["cluster_bh"] = len(cl)
            if cl:
                rad, vert = [], []
                p = xyz[in_bh]
                for idx in cl:
                    q = p[idx]
                    ctr = q[:, :2].mean(axis=0)
                    rad.append(float(np.median(np.hypot(q[:, 0] - ctr[0],
                                                        q[:, 1] - ctr[1]))))
                    vert.append(float(q[:, 2].max() - q[:, 2].min()))
                r["radius_med_cm"] = round(100 * float(np.median(rad)), 1)
                r["cluster_z_spanne_m"] = round(float(np.median(vert)), 2)
        rows.append(r)

    hdr = ("Kl.  Anteil  H_med  H_p95  %inBH  Cluster  r_med   z-Spanne")
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['klasse']:3}  {r['anteil_pct']:5.2f}%  "
              f"{r['hoehe_median_m']:5.2f}  {r['hoehe_p95_m']:5.1f}  "
              f"{r['anteil_bh_pct']:5.2f}  {r.get('cluster_bh','-'):>7}  "
              f"{r.get('radius_med_cm','-'):>5}   {r.get('cluster_z_spanne_m','-'):>5}")
    print("\nLesehilfe: Boden = H_med ~ 0 und grosse Flaeche; Stamm = viele kompakte "
          "Cluster\nim Brusthoehen-Band (kleiner r_med) bei hohem H_p95; "
          "Krone = H_med hoch, wenig in BH.")

    if args.out:
        Path(args.out).write_text(json.dumps(rows, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()
