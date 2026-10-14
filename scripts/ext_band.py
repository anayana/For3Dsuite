#!/usr/bin/env python3
"""ext_band.py -- Brusthoehenband aus einer grossen LAZ-Wolke schneiden (fuer CI).

Zwei Durchgaenge in Bloecken (passt auch fuer 100+ Mio. Punkte in wenig RAM):
  1. Gelaendehoehe je 1-m-Zelle = 2. Perzentil-Naeherung (Minimum der Zelle nach
     Verwerfen des tiefsten Punkts je Block)
  2. Punkte mit Hoehe ueber Grund in [lo, hi] behalten, auf 1-cm-Voxel ausduennen.
Gespeichert: npz mit float32 x, y, z, hag (Hoehe ueber Grund) und uint8 cls
(Label-Dimension, falls vorhanden; sonst 0).

  python scripts/ext_band.py plot_06.laz --out extdata/segforests/plot_06_band.npz
"""
import argparse
from pathlib import Path

import laspy
import numpy as np


def label_dim(f):
    names = [d.name for d in f.header.point_format.dimensions]
    for c in ("classification", "label", "Label", "scalar_label", "class"):
        if c in names:
            return c
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("laz"); ap.add_argument("--out", required=True)
    ap.add_argument("--lo", type=float, default=0.8); ap.add_argument("--hi", type=float, default=1.8)
    ap.add_argument("--voxel", type=float, default=0.01); ap.add_argument("--cell", type=float, default=1.0)
    ap.add_argument("--chunk", type=int, default=5_000_000)
    a = ap.parse_args()

    with laspy.open(a.laz) as f:
        h = f.header; x0, y0 = h.mins[0], h.mins[1]
        nx = int((h.maxs[0] - x0) / a.cell) + 1; ny = int((h.maxs[1] - y0) / a.cell) + 1
        gmin = np.full(nx * ny, np.inf)
        for pts in f.chunk_iterator(a.chunk):
            x, y, z = np.asarray(pts.x), np.asarray(pts.y), np.asarray(pts.z)
            k = ((x - x0) / a.cell).astype(np.int64) * ny + ((y - y0) / a.cell).astype(np.int64)
            np.minimum.at(gmin, k, z)
    # Loecher (Zellen ohne Punkte) mit Nachbarmedian fuellen
    g = gmin.reshape(nx, ny)
    for _ in range(5):
        bad = ~np.isfinite(g)
        if not bad.any():
            break
        p = np.pad(g, 1, constant_values=np.inf)
        nb = np.stack([p[1 + dx:1 + dx + nx, 1 + dy:1 + dy + ny] for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
        nb = np.where(np.isfinite(nb), nb, np.nan)
        with np.errstate(all="ignore"):
            fill = np.nanmedian(nb, axis=0)
        g[bad] = fill[bad]
    gmin = g.ravel()

    keep = {k: [] for k in ("x", "y", "z", "hag", "cls")}
    seen = set()
    with laspy.open(a.laz) as f:
        ld = label_dim(f)
        for pts in f.chunk_iterator(a.chunk):
            x, y, z = np.asarray(pts.x), np.asarray(pts.y), np.asarray(pts.z)
            k = ((x - x0) / a.cell).astype(np.int64) * ny + ((y - y0) / a.cell).astype(np.int64)
            hag = z - gmin[k]
            m = (hag >= a.lo) & (hag <= a.hi)
            if not m.any():
                continue
            vx = np.floor(np.stack([x[m], y[m], z[m]], 1) / a.voxel).astype(np.int64)
            key = (vx[:, 0] * 73856093) ^ (vx[:, 1] * 19349663) ^ (vx[:, 2] * 83492791)
            _, first = np.unique(key, return_index=True)
            new = np.array([i for i in first if key[i] not in seen], dtype=np.int64)
            seen.update(key[new].tolist())
            idx = np.flatnonzero(m)[new]
            keep["x"].append(x[idx].astype(np.float32)); keep["y"].append(y[idx].astype(np.float32))
            keep["z"].append(z[idx].astype(np.float32)); keep["hag"].append(hag[idx].astype(np.float32))
            keep["cls"].append(np.asarray(getattr(pts, ld))[idx].astype(np.uint8) if ld else np.zeros(len(idx), np.uint8))
    out = {k: np.concatenate(v) for k, v in keep.items()}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, **out, label_dim=np.array(ld or ""))
    print(f"-> {a.out}: {len(out['x'])} Punkte im Band {a.lo}-{a.hi} m (Label: {ld})")


if __name__ == "__main__":
    main()
