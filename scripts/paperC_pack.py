#!/usr/bin/env python3
"""paperC_pack.py -- HELIOS-Ausgabe je Standpunkt auf das Brusthoehenband eindampfen.

HELIOS schreibt je Leg eine ASCII-Datei (x y z intensity echo_width return_no
n_returns fullwave_idx hit_object_id class gps_time), bei 0,06 Grad rund 4 Mio.
Punkte bzw. 330 MB. Fuer die Abdeckungs- und BHD-Auswertung reicht das Band
0,9-1,7 m ueber Grund auf Stammobjekten. Gespeichert wird je Leg ein npz
(float32 x, y, z; int32 obj); die Textdatei wird danach geloescht.

  python scripts/paperC_pack.py data/paperC/S1b/out --dest data/paperC/S1b/legs
"""
import argparse
import glob
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

Z_LO, Z_HI = 0.9, 1.7


def pack(src, dest):
    parts = []
    for ch in pd.read_csv(src, sep=" ", header=None, usecols=[0, 1, 2, 8], names=["x", "y", "z", "obj"],
                          dtype={"x": np.float32, "y": np.float32, "z": np.float32, "obj": np.int32}, chunksize=2_000_000):
        parts.append(ch[(ch.obj > 0) & (ch.z > Z_LO) & (ch.z < Z_HI)])
    d = pd.concat(parts)
    np.savez_compressed(dest, x=d.x.values, y=d.y.values, z=d.z.values, obj=d.obj.values)
    return len(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir", help="HELIOS-Ausgabeordner (sucht leg*_points.xyz rekursiv)")
    ap.add_argument("--dest", required=True)
    ap.add_argument("--keep", action="store_true", help="Textdateien nicht loeschen")
    args = ap.parse_args()
    dest = Path(args.dest); dest.mkdir(parents=True, exist_ok=True)
    for f in sorted(glob.glob(os.path.join(args.outdir, "**", "leg*_points.xyz"), recursive=True)):
        leg = int(re.search(r"leg(\d+)_points", f).group(1))
        n = pack(f, dest / f"leg{leg:03d}.npz")
        print(f"leg {leg:3d}: {n} Punkte im Band", flush=True)
        if not args.keep:
            os.remove(f)


if __name__ == "__main__":
    main()
