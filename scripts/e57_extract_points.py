#!/usr/bin/env python3
"""e57_extract_points.py -- Punktwolke (XYZ+RGB+Intensitaet) aus E57 nach LAS.

Nutzt pye57 (libE57Format); read_scan wendet die Scan-Pose an, d. h. die
Ausgabe liegt im selben Koordinatensystem wie die Kamera-Posen aus
e57_extract_images.py — Bild und Wolke sind damit koregistriert.

Nutzung:
  python e57_extract_points.py <datei.e57> <out.las> [--subsample N]
"""
import argparse

import laspy
import numpy as np
import pye57


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("e57")
    ap.add_argument("out")
    ap.add_argument("--subsample", type=int, default=1,
                    help="nur jeden N-ten Punkt schreiben (Default 1 = alle)")
    ap.add_argument("--scan", type=int, default=0, help="Scan-Index (Default 0)")
    args = ap.parse_args()

    e = pye57.E57(args.e57)
    d = e.read_scan(args.scan, ignore_missing_fields=True, colors=True, intensity=True)
    n = len(d["cartesianX"])
    sel = slice(None, None, max(1, args.subsample))

    x, y, z = (d[k][sel] for k in ("cartesianX", "cartesianY", "cartesianZ"))
    header = laspy.LasHeader(point_format=2, version="1.2")  # Format 2 = RGB
    header.offsets = [float(x.min()), float(y.min()), float(z.min())]
    header.scales = [0.001, 0.001, 0.001]
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    if "intensity" in d:
        i = d["intensity"][sel].astype(np.float64)
        rng = i.max() - i.min()
        las.intensity = ((i - i.min()) / (rng if rng > 0 else 1) * 65535).astype(np.uint16)
    if "colorRed" in d:
        for las_f, e57_f in (("red", "colorRed"), ("green", "colorGreen"), ("blue", "colorBlue")):
            c = d[e57_f][sel].astype(np.uint16)
            setattr(las, las_f, c * 257 if c.max() <= 255 else c)  # 8 -> 16 Bit
    las.write(args.out)
    print(f"-> {args.out}: {len(x):,} von {n:,} Punkten"
          f" (subsample {args.subsample}), RGB={'colorRed' in d}")


if __name__ == "__main__":
    main()
