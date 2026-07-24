#!/usr/bin/env python3
"""points_to_splat.py -- Web-Punktwolke (.bin) -> 3D-Gaussian-Splatting-.ply.

Erzeugt aus dem kompakten .bin-Format (float32-XYZ-Block + uint8-RGB-Block, wie
pointcloud_web.py) eine .ply im INRIA-3DGS-Format: jeder Punkt wird ein kleiner,
runder, opaker Gaussian in seiner Punktfarbe. Das ist KEIN trainiertes Splatting
(keine Neuansichts-Synthese), sondern eine Punktwolke-als-Gaussians -- als
Platzhalter/Testfall fuer den Splat-Viewer, bis ein echtes 3DGS-Ergebnis vorliegt.

Die erzeugte .ply liest jeder 3DGS-Viewer (SuperSplat, mkkellogg/gaussian-splats-3d).

  python points_to_splat.py cloud_lite.bin out.ply [--count N] [--max 120000] [--size 0.03]
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

C0 = 0.28209479177387814   # SH-DC-Basis: color = 0.5 + C0 * f_dc


def read_bin(path, count):
    raw = np.fromfile(path, dtype=np.uint8)
    xyz = raw[: count * 12].view("<f4").reshape(count, 3)
    rgb = raw[count * 12: count * 12 + count * 3].reshape(count, 3)
    return xyz.astype(np.float32), rgb.astype(np.float32)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("bin")
    ap.add_argument("out")
    ap.add_argument("--count", type=int, help="Punktzahl (Default: aus <bin>.json)")
    ap.add_argument("--max", type=int, default=120000, help="max. Gaussians (Subsampling)")
    ap.add_argument("--size", type=float, default=0.03, help="Gaussian-Radius [m]")
    args = ap.parse_args()

    count = args.count
    if count is None:
        meta = json.loads(Path(args.bin).with_suffix(".json").read_text())
        count = meta["count"]
    xyz, rgb = read_bin(args.bin, count)

    if len(xyz) > args.max:
        idx = np.random.default_rng(0).choice(len(xyz), args.max, replace=False)
        xyz, rgb = xyz[idx], rgb[idx]
    n = len(xyz)

    f_dc = (rgb / 255.0 - 0.5) / C0                       # Farbe -> SH-DC
    opacity = np.full((n, 1), 8.0, np.float32)            # logit(~1) = opak
    scale = np.full((n, 3), math.log(args.size), np.float32)   # log-Radius, rund
    rot = np.tile(np.array([1, 0, 0, 0], np.float32), (n, 1))  # Identitaets-Quaternion
    normals = np.zeros((n, 3), np.float32)

    cols = (["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2", "opacity"]
            + ["scale_0", "scale_1", "scale_2", "rot_0", "rot_1", "rot_2", "rot_3"])
    data = np.concatenate([xyz, normals, f_dc, opacity, scale, rot], 1).astype(np.float32)
    el = np.empty(n, dtype=[(c, "<f4") for c in cols])
    for i, c in enumerate(cols):
        el[c] = data[:, i]

    with open(args.out, "wb") as f:
        f.write(b"ply\nformat binary_little_endian 1.0\n")
        f.write(f"element vertex {n}\n".encode())
        for c in cols:
            f.write(f"property float {c}\n".encode())
        f.write(b"end_header\n")
        f.write(el.tobytes())
    print(f"-> {args.out}: {n:,} Gaussians ({Path(args.out).stat().st_size/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
