#!/usr/bin/env python3
"""e57_merge.py -- mehrere registrierte E57 zu EINER Analyse-Wolke verschmelzen.

e57_scene.py baut aus denselben Dateien die *Web*-Wolke (auf 160k/700k
heruntergezogen, um den Ursprung rezentriert). Fuer die Auswertung (Stammfit,
BHD-Verfahren, QSM, ITCD) ist das zu duenn: dort zaehlt jeder Punkt am Stamm.
Dieses Skript schreibt daher die dichte Wolke als .npz --- ausgeduennt nur mit
einem feinen Voxel (Default 1 cm, gegen Mehrfachtreffer derselben Flaeche aus
verschiedenen Standpunkten) und in WELT-Koordinaten des registrierten E57-Frames.

Alle nachgelagerten Skripte rechnen in genau diesem Frame; die Szene haelt ihren
Bin-Offset in source.origin_xyz (welt = bin + origin), Marker liegen in Welt.

  python scripts/e57_merge.py data/Renon/e57/*.e57 --out data/Renon/_analysis.npz

Ausgabe: xyz (float32, relativ zu 'shift' im Archiv), rgb (uint8), shift
(float64) --- welt = xyz + shift. Der Shift haelt die float32-Aufloesung im
Millimeterbereich, auch wenn der E57-Frame weit vom Nullpunkt liegt.
"""
import argparse
from pathlib import Path

import numpy as np
import pye57


def voxel_unique(xyz, voxel):
    """Index je belegtem Voxel (erster Treffer) -- ohne die Wolke zu sortieren."""
    k = np.floor(xyz / voxel).astype(np.int64)
    key = (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)
    _, idx = np.unique(key, return_index=True)
    return idx


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("e57", nargs="+", help="registrierte E57-Standpunkte (gleicher Frame)")
    ap.add_argument("--out", required=True, help="Ziel-.npz")
    ap.add_argument("--voxel", type=float, default=0.01,
                    help="Voxelweite der Ausduennung in m (Default 1 cm)")
    args = ap.parse_args()

    parts_xyz, parts_rgb, n_raw = [], [], 0
    for path in args.e57:
        d = pye57.E57(path).read_scan(0, ignore_missing_fields=True, colors=True)
        p = np.c_[d["cartesianX"], d["cartesianY"], d["cartesianZ"]].astype(np.float64)
        c = np.c_[d["colorRed"], d["colorGreen"], d["colorBlue"]].astype(np.float64)
        if c.max() > 255:                     # 16-bit-Farbe -> 8 bit
            c = c / c.max() * 255
        n_raw += len(p)
        # Schon je Standpunkt ausduennen: sonst liegen 28,8 Mio Punkte gleichzeitig
        # als float64 im Speicher (~700 MB nur fuer die Koordinaten).
        idx = voxel_unique(p, args.voxel)
        parts_xyz.append(p[idx])
        parts_rgb.append(c[idx].astype(np.uint8))
        print(f"gelesen: {len(p):,} Punkte aus {Path(path).name} "
              f"-> {len(idx):,} nach {args.voxel*100:.0f}-cm-Voxel")

    xyz = np.concatenate(parts_xyz)
    rgb = np.concatenate(parts_rgb)
    del parts_xyz, parts_rgb
    # Zweiter Durchgang ueber die vereinigte Wolke: entfernt die Ueberlappung
    # zwischen den Standpunkten (dieselbe Flaeche mehrfach gescannt).
    idx = voxel_unique(xyz, args.voxel)
    over = 100.0 * (1 - len(idx) / len(xyz))
    xyz, rgb = xyz[idx], rgb[idx]
    print(f"verschmolzen: {n_raw:,} roh -> {len(xyz):,} Punkte "
          f"({over:.0f}% Ueberlappung zwischen den Standpunkten entfernt)")

    shift = np.floor(xyz.min(axis=0))          # ganzzahlig: bleibt nachvollziehbar
    local = (xyz - shift).astype(np.float32)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez(out, xyz=local, rgb=rgb, shift=shift,
             voxel=np.float64(args.voxel), n_raw=np.int64(n_raw))
    lo, hi = xyz.min(0), xyz.max(0)
    print(f"-> {out} ({out.stat().st_size/1e6:.0f} MB)")
    print(f"   Welt-bbox  x {lo[0]:.1f}..{hi[0]:.1f}  y {lo[1]:.1f}..{hi[1]:.1f}  "
          f"z {lo[2]:.1f}..{hi[2]:.1f}")


if __name__ == "__main__":
    main()
