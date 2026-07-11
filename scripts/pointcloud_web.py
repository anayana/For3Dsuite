#!/usr/bin/env python3
"""pointcloud_web.py -- E57/LAS -> kompakte Web-Punktwolke fuer den 3D-Viewer.

Erzeugt eine Binaerdatei (XYZ als float32 + RGB als uint8, interleaved) plus
ein Meta-JSON (Anzahl, Bounding-Box, Ursprung). Die Koordinaten werden auf den
Scan-Ursprung zentriert, damit sie mit den Panorama-Markern im selben Bezug
liegen. Fuer sehr grosse Wolken per Voxel-Gitter ausgeduennt (LOD-frei; fuer
echtes LOD PotreeConverter im Worker nutzen, siehe platform/README.md).

Format der .bin (little-endian, blockweise -- erlaubt zero-copy Float32Array
im Browser): erst alle Positionen (float32 x,y,z je Punkt), dann alle Farben
(uint8 r,g,b je Punkt). Punktzahl steht im Meta-JSON.

Nutzung:
  python pointcloud_web.py <datei.e57|.las> <out.bin> [--origin X Y Z]
      [--max-points 800000] [--voxel 0.05] [--radius 25]
"""
import argparse
import json
import struct
from pathlib import Path

import numpy as np


def load(path):
    if path.lower().endswith(".e57"):
        import pye57
        d = pye57.E57(path).read_scan(0, ignore_missing_fields=True,
                                      colors=True, intensity=True)
        xyz = np.c_[d["cartesianX"], d["cartesianY"], d["cartesianZ"]].astype(np.float32)
        if "colorRed" in d:
            rgb = np.c_[d["colorRed"], d["colorGreen"], d["colorBlue"]].astype(np.float32)
        else:
            rgb = None
        return xyz, rgb
    import laspy
    las = laspy.read(path)
    xyz = np.c_[las.x, las.y, las.z].astype(np.float32)
    rgb = None
    if hasattr(las, "red"):
        rgb = np.c_[las.red, las.green, las.blue].astype(np.float32)
        if rgb.max() > 255:
            rgb /= 257.0
    return xyz, rgb


def voxel_downsample(xyz, rgb, voxel):
    keys = np.floor(xyz / voxel).astype(np.int64)
    _, idx = np.unique(keys[:, 0] * 73856093 ^ keys[:, 1] * 19349663 ^ keys[:, 2] * 83492791,
                       return_index=True)
    return xyz[idx], (rgb[idx] if rgb is not None else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cloud"); ap.add_argument("out")
    ap.add_argument("--origin", nargs=3, type=float, metavar=("X", "Y", "Z"))
    ap.add_argument("--radius", type=float, default=25.0)
    ap.add_argument("--max-points", type=int, default=800_000)
    ap.add_argument("--voxel", type=float, default=0.05)
    args = ap.parse_args()

    xyz, rgb = load(args.cloud)
    print(f"{len(xyz):,} Punkte geladen")

    if args.origin:
        o = np.array(args.origin, np.float32)
        m = np.hypot(xyz[:, 0] - o[0], xyz[:, 1] - o[1]) <= args.radius
        xyz, rgb = xyz[m], (rgb[m] if rgb is not None else None)
    else:
        o = xyz.mean(0)

    xyz, rgb = voxel_downsample(xyz, rgb, args.voxel)
    if len(xyz) > args.max_points:
        sel = np.random.default_rng(0).choice(len(xyz), args.max_points, replace=False)
        xyz, rgb = xyz[sel], (rgb[sel] if rgb is not None else None)
    print(f"{len(xyz):,} Punkte nach Ausduennung (voxel {args.voxel} m)")

    xyz = xyz - o                                  # auf Ursprung zentrieren
    if rgb is None:
        rgb = np.full((len(xyz), 3), 180, np.uint8)
    rgb = np.clip(rgb, 0, 255).astype(np.uint8)

    # Blockweise: erst float32-Positionen, dann uint8-Farben (zero-copy im Browser)
    Path(args.out).write_bytes(xyz.astype("<f4").tobytes() + rgb.tobytes())

    meta = {
        "format": "xyz_f32_rgb_u8_blocks",
        "count": int(len(xyz)),
        "origin_xyz": [float(c) for c in o],
        "bbox_min": [float(c) for c in xyz.min(0)],
        "bbox_max": [float(c) for c in xyz.max(0)],
    }
    Path(args.out).with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(f"-> {args.out} ({len(xyz)*15/1e6:.1f} MB) + {Path(args.out).with_suffix('.json').name}")


if __name__ == "__main__":
    main()
