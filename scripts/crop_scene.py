#!/usr/bin/env python3
"""crop_scene.py -- Web-Splat einer Szene auf das Gebaeude zuschneiden.

Entfernt Gaussians ausserhalb der bbox der Szene (+ Rand) und zu grosse Gaussians (Himmel, Baeume,
Hintergrund bilden sonst eine Huelle um das Gebaeude). Arbeitet in den verschobenen Koordinaten
der Szene (scene.json: splat.bbox, splat.offset bereits abgezogen).

  python scripts/crop_scene.py docs/data/scene-pellis-2-osa.json docs/media/scenes/pellis-2-osa/2_osa.ply \
      [--margin 3] [--max-scale 0.5]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean_splat import read_ply, write_ply  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("scene"); ap.add_argument("ply")
    ap.add_argument("--margin", type=float, default=3.0, help="Rand um die bbox [m]")
    ap.add_argument("--max-scale", type=float, default=0.5, help="max. Gaussian-Radius [m]")
    a = ap.parse_args()
    bb = json.load(open(a.scene))["splat"]["bbox"]
    lo, hi = np.array(bb["bbox_min"]) - a.margin, np.array(bb["bbox_max"]) + a.margin
    arr, names = read_ply(Path(a.ply))
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1)
    sc = np.exp(np.stack([arr[f"scale_{i}"] for i in range(3)], 1)).max(1)
    keep = np.all((xyz >= lo) & (xyz <= hi), 1) & (sc <= a.max_scale)
    write_ply(Path(a.ply), arr[keep], names)
    print(f"{a.ply}: {keep.sum():,}/{len(arr):,} Gaussians behalten")


if __name__ == "__main__":
    main()
