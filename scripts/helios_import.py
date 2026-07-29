#!/usr/bin/env python3
"""helios_import.py -- synthetische HELIOS++-Wolke -> begehbare Suite-Szene.

Liest die leg*_points.xyz-Ausgabe eines HELIOS++-Laufs (scripts/helios_scene.py),
fasst die Standpunkte zusammen, faerbt nach Hoehe (bzw. Boden/Vegetation ueber die
getroffene Objekt-ID) und schreibt das kompakte Web-Format der Suite (float32-xyz +
uint8-rgb, Stufen lite/full) samt scene.json. Damit steht der SYNTHETISCHE Scan
neben den echten Szenen -- der Beleg fuer den Strang "Inventur -> HELIOS++"
(Exposé 2g): eine Punktwolke mit BEKANNTER Wahrheit, weil jeder Baum gesetzt wurde.

  python scripts/helios_import.py <helios-output-dir> [--id renon-helios-synth]
      [--voxel 0.03]
"""
import argparse
import glob
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
MEDIA = REPO / "platform" / "dev-data" / "media"
LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]


def height_ramp(z):
    """Terrain-Farbverlauf ueber die Hoehe (dunkelblau->gruen->gelb->weiss)."""
    lo, hi = np.percentile(z, 2), np.percentile(z, 98)
    t = np.clip((z - lo) / (hi - lo if hi > lo else 1), 0, 1)
    stops = np.array([[40, 55, 95], [40, 120, 105], [140, 190, 80],
                      [235, 220, 120], [250, 250, 250]], np.float32)
    pos = np.linspace(0, 1, len(stops))
    return np.stack([np.interp(t, pos, stops[:, k]) for k in range(3)], -1)


def voxel_downsample(xyz, voxel):
    keys = np.floor(xyz / voxel).astype(np.int64)
    _, idx = np.unique(keys[:, 0] * 73856093 ^ keys[:, 1] * 19349663
                       ^ keys[:, 2] * 83492791, return_index=True)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--id", default="renon-helios-synth")
    ap.add_argument("--voxel", type=float, default=0.03)
    args = ap.parse_args()

    legs = sorted(glob.glob(os.path.join(args.outdir, "**", "leg*_points.xyz"),
                            recursive=True))
    if not legs:
        raise SystemExit(f"keine leg*_points.xyz unter {args.outdir}")
    print(f"{len(legs)} Standpunkte: {[os.path.basename(l) for l in legs]}")

    # Spalten der HELIOS++-XYZ: x y z intensity ... (nur xyz noetig)
    parts = []
    for l in legs:
        a = np.loadtxt(l, usecols=(0, 1, 2), dtype=np.float64)
        parts.append(a)
        print(f"  {os.path.basename(l)}: {len(a):,}")
    xyz = np.concatenate(parts)
    print(f"gesamt {len(xyz):,} Punkte")

    idx = voxel_downsample(xyz, args.voxel)
    xyz = xyz[idx]
    print(f"nach Voxel-Ausduennung ({args.voxel} m): {len(xyz):,}")

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(),
                       np.percentile(xyz[:, 2], 1)])
    rgb_full = height_ramp(xyz[:, 2])
    local = (xyz - origin).astype(np.float32)

    dest = MEDIA / "scenes" / args.id
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        sel = (rng.choice(len(local), maxpts, replace=False)
               if len(local) > maxpts else np.arange(len(local)))
        p = np.ascontiguousarray(local[sel], "<f4")
        c = np.clip(rgb_full[sel], 0, 255).astype(np.uint8)
        (dest / fname).write_bytes(p.tobytes() + c.tobytes())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{args.id}/{fname}",
                       "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        print(f"  {label}: {len(p):,} Punkte")
        if lid == "lite":
            W = H = 640
            img = np.full((H, W, 3), 13, np.uint8)
            nx = ((p[:, 0] - p[:, 0].min()) / max(np.ptp(p[:, 0]), 1e-6)
                  * (W - 1)).astype(int)
            ny = ((p[:, 1] - p[:, 1].min()) / max(np.ptp(p[:, 1]), 1e-6)
                  * (H - 1)).astype(int)
            img[H - 1 - ny, nx] = c
            Image.fromarray(img).save(dest / "thumb.jpg", quality=85)

    scene = {
        "id": args.id,
        "title": "Renon — synthetischer TLS-Scan (HELIOS++)",
        "description": (
            f"Mit HELIOS++ SIMULIERTER terrestrischer Laserscan aus der "
            f"Einzelbaum-Inventur (87 Baeume) desselben Renon-Standorts: prozedurale "
            f"Baummodelle (Stamm + Krone, aus BHD/Hoehe) an ihren gemessenen "
            f"Positionen, von mehreren TLS-Standpunkten abgetastet. {len(xyz):,} "
            f"Punkte (nach Ausduennung), nach Hoehe eingefaerbt. Der Wert liegt in der "
            f"BEKANNTEN Wahrheit -- jeder Baumparameter ist gesetzt, nicht geschaetzt: "
            f"Grundlage fuer Benchmark der Inventur-Algorithmen und fuer Szenarien "
            f"(via TreeGrOSS projizierte Bestaende erneut scannen). Kein reales "
            f"Messdatum. Simulator: HELIOS++ (3dgeo Heidelberg); Szene aus "
            f"scripts/helios_scene.py."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.id}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "helios-synthetic",
                   "origin_xyz": [float(c) for c in origin],
                   "dataset": "Synthetischer TLS-Scan (HELIOS++) der Renon-Inventur",
                   "url": "https://github.com/3dgeo-heidelberg/helios",
                   "gps": {"lat": 46.58686, "lon": 11.43369}},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{args.id}' gebaut ({len(xyz):,} Punkte)")


if __name__ == "__main__":
    main()
