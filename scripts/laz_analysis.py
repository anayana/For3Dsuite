#!/usr/bin/env python3
"""laz_analysis.py -- grosse Plot-LAZ zur Analyse-Wolke (.npz) ausduennen.

Gegenstueck zu e57_merge.py fuer LAZ-Plots (SegmentedForests u. ae.) und schreibt
DASSELBE .npz-Format, damit die ganze Kette -- inventory_from_cloud.py,
dbh_methods.py, itcd_cloud.py, qsm_cloud.py -- unveraendert weiterlaeuft:

    xyz (float32, relativ zu 'shift')   rgb (uint8)   shift (float64)

Zusaetzlich, wenn vorhanden: 'cls' -- das SEMANTISCHE LABEL je Punkt. Bei
SegmentedForests steckt es in der Extra-Dimension 'Class' (manuell annotiert);
sonst wird die LAS-classification genommen. Das ist die Ground Truth, gegen die
sich Detektion und Segmentierung erstmals messen lassen.

Gelesen wird BLOCKWEISE: 77 Mio. Punkte als float64-XYZ waeren 1,8 GB allein fuer
die Koordinaten. Jeder Block wird sofort auf das Voxelgitter reduziert.

  python scripts/laz_analysis.py data/segforests/plot_06.laz \\
      --out data/segforests/plot_06_analysis.npz --voxel 0.01
"""
import argparse
from pathlib import Path

import laspy
import numpy as np


def voxel_unique(xyz, voxel):
    k = np.floor(xyz / voxel).astype(np.int64)
    key = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
    _, idx = np.unique(key, return_index=True)
    return idx


def pick_class_dim(header):
    """Extra-Dimension mit dem semantischen Label finden."""
    names = {d.name for d in header.point_format.dimensions}
    for cand in ("Class", "class", "label", "Label", "semantic"):
        if cand in names:
            return cand
    return "classification"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("laz")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voxel", type=float, default=0.01)
    ap.add_argument("--chunk", type=int, default=4_000_000,
                    help="Punkte je Lesedurchgang")
    ap.add_argument("--class-dim", help="Name der Label-Dimension (sonst automatisch)")
    args = ap.parse_args()

    with laspy.open(args.laz) as f:
        hdr = f.header
        cdim = args.class_dim or pick_class_dim(hdr)
        has_rgb = "red" in {d.name for d in hdr.point_format.dimensions}
        print(f"{hdr.point_count:,} Punkte, Format {hdr.point_format.id}, "
              f"Label-Dimension '{cdim}', RGB {'ja' if has_rgb else 'nein'}")

        parts_xyz, parts_rgb, parts_cls, n_raw = [], [], [], 0
        for pts in f.chunk_iterator(args.chunk):
            p = np.c_[pts.x, pts.y, pts.z].astype(np.float64)
            n_raw += len(p)
            idx = voxel_unique(p, args.voxel)      # Block sofort reduzieren
            parts_xyz.append(p[idx])
            if has_rgb:
                c = np.c_[pts.red, pts.green, pts.blue].astype(np.float64)
                if c.max() > 255:                  # 16-bit-Farbe -> 8 bit
                    c = c / 65535.0 * 255
                parts_rgb.append(c[idx].astype(np.uint8))
            parts_cls.append(np.asarray(pts[cdim])[idx].astype(np.uint8))
            print(f"  gelesen {n_raw:,} -> {sum(len(a) for a in parts_xyz):,}",
                  flush=True)

    xyz = np.concatenate(parts_xyz)
    cls = np.concatenate(parts_cls)
    rgb = (np.concatenate(parts_rgb) if has_rgb
           else np.full((len(xyz), 3), 160, np.uint8))
    del parts_xyz, parts_rgb, parts_cls

    # Zweiter Durchgang: die Bloecke ueberlappen sich am Rand
    idx = voxel_unique(xyz, args.voxel)
    xyz, rgb, cls = xyz[idx], rgb[idx], cls[idx]
    print(f"{n_raw:,} roh -> {len(xyz):,} nach {args.voxel*100:.0f}-cm-Voxel")

    shift = np.floor(xyz.min(axis=0))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, xyz=(xyz - shift).astype(np.float32), rgb=rgb, cls=cls,
             shift=shift, voxel=np.float64(args.voxel), n_raw=np.int64(n_raw))
    lo, hi = xyz.min(0), xyz.max(0)
    print(f"-> {out} ({out.stat().st_size/1e6:.0f} MB)")
    print(f"   bbox  x {lo[0]:.1f}..{hi[0]:.1f}  y {lo[1]:.1f}..{hi[1]:.1f}  "
          f"z {lo[2]:.1f}..{hi[2]:.1f}")
    vals, cnt = np.unique(cls, return_counts=True)
    print("   Labels:", ", ".join(f"{v}:{c:,}" for v, c in zip(vals, cnt)))


if __name__ == "__main__":
    main()
