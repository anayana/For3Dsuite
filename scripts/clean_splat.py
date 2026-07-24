#!/usr/bin/env python3
"""clean_splat.py -- Hintergrund-/Floater-Splats aus einer 3DGS-.ply entfernen.

Ersetzt das manuelle Wegschneiden in SuperSplat: bei Mip-NeRF-360-artigen Szenen
sind die stoerenden weissen Fetzen weit entfernte, grosse, halbtransparente
Gaussians. Dieses Skript liest eine INRIA-3DGS-.ply, wirft raus:
  - raeumliche Ausreisser (ausserhalb des --keep-Perzentil-Kerns der Punktwolke)
  - sehr grosse Gaussians (--max-scale, in m) -- typische Hintergrund-Blobs
  - fast durchsichtige (--min-opacity nach Sigmoid)
und schreibt eine bereinigte .ply mit denselben Feldern.

  python clean_splat.py stump_gaussians.ply stump_clean.ply
      [--keep 96] [--max-scale 0.6] [--min-opacity 0.15]
"""
import argparse
import struct

import numpy as np


def read_ply(path):
    with open(path, "rb") as f:
        assert f.readline().strip() == b"ply"
        fmt = f.readline().strip()
        assert b"binary_little_endian" in fmt, "nur binary_little_endian"
        n, names = None, []
        while True:
            ln = f.readline().strip()
            if ln.startswith(b"element vertex"):
                n = int(ln.split()[-1])
            elif ln.startswith(b"property"):
                names.append(ln.split()[-1].decode())
            elif ln == b"end_header":
                break
        dt = np.dtype([(nm, "<f4") for nm in names])
        arr = np.frombuffer(f.read(dt.itemsize * n), dtype=dt, count=n)
    return arr, names


def write_ply(path, arr, names):
    with open(path, "wb") as f:
        f.write(b"ply\nformat binary_little_endian 1.0\n")
        f.write(f"element vertex {len(arr)}\n".encode())
        for nm in names:
            f.write(f"property float {nm}\n".encode())
        f.write(b"end_header\n")
        f.write(arr.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("inp"); ap.add_argument("out")
    ap.add_argument("--keep", type=float, default=96,
                    help="raeumliches Kern-Perzentil (Punkte weiter draussen fliegen raus)")
    ap.add_argument("--max-scale", type=float, default=0.6, help="max. Gaussian-Radius [m]")
    ap.add_argument("--min-opacity", type=float, default=0.12, help="min. Deckkraft (0..1)")
    args = ap.parse_args()

    arr, names = read_ply(args.inp)
    n0 = len(arr)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1)
    c = np.median(xyz, 0)
    d = np.linalg.norm(xyz - c, axis=1)
    keep = d <= np.percentile(d, args.keep)                 # raeumlicher Kern

    scl = [k for k in names if k.startswith("scale_")]
    if scl:
        smax = np.exp(np.stack([arr[k] for k in scl], 1)).max(1)   # log -> m
        keep &= smax <= args.max_scale
    if "opacity" in names:
        op = 1.0 / (1.0 + np.exp(-arr["opacity"]))          # logit -> 0..1
        keep &= op >= args.min_opacity

    out = arr[keep]
    write_ply(args.out, out, names)
    print(f"-> {args.out}: {len(out):,}/{n0:,} Gaussians behalten "
          f"({100*len(out)/n0:.1f}%), {n0-len(out):,} Floater/Hintergrund entfernt")


if __name__ == "__main__":
    main()
