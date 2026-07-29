#!/usr/bin/env python3
"""e57_scene.py -- RGB-Punktwolke aus einer E57 als begehbare Suite-Szene.

Liest die Punktwolke (cartesianXYZ + colorRGB) via pye57, duennt voxelbasiert aus,
rezentriert auf den eigenen Schwerpunkt (z-up wie die uebrigen Renon-Szenen) und
schreibt das kompakte Web-Format der Suite (float32-xyz + uint8-rgb, Stufen
lite/full) samt scene.json und Thumbnail. So wird eine weitere reale Renon-E57
(z. B. Setup 002) zur echten RGB-Punktwolken-Szene -- kein synthetischer Scan,
sondern gemessene Farbe je Punkt.

  python scripts/e57_scene.py <szenen-id> <datei.e57> [<datei2.e57> ...] \
      [--title "..."] [--voxel 0.02]

Mehrere E57 desselben (registrierten) Frames werden VERSCHMOLZEN -- das fuellt die
Scan-Schatten des Einzelstandpunkts (weniger Verdeckung, dichtere Wolke).
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pye57
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
MEDIA = REPO / "platform" / "dev-data" / "media"
LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]


def voxel_idx(xyz, voxel):
    k = np.floor(xyz / voxel).astype(np.int64)
    _, idx = np.unique(k[:, 0] * 73856093 ^ k[:, 1] * 19349663 ^ k[:, 2] * 83492791,
                       return_index=True)
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("e57", nargs="+", help="eine oder mehrere E57 (gleicher Frame -> verschmolzen)")
    ap.add_argument("--title", default=None)
    ap.add_argument("--voxel", type=float, default=0.02)
    args = ap.parse_args()

    xyz_parts, rgb_parts = [], []
    for path in args.e57:
        e = pye57.E57(path)
        d = e.read_scan(0, ignore_missing_fields=True, colors=True)
        p = np.c_[d["cartesianX"], d["cartesianY"], d["cartesianZ"]].astype(np.float64)
        c = np.c_[d["colorRed"], d["colorGreen"], d["colorBlue"]]
        if c.max() > 255:                       # 16-bit-Farbe -> 8 bit
            c = (c.astype(np.float64) / c.max() * 255)
        xyz_parts.append(p); rgb_parts.append(c.astype(np.uint8))
        print(f"gelesen: {len(p):,} Punkte aus {Path(path).name}")
    xyz = np.concatenate(xyz_parts)
    rgb = np.concatenate(rgb_parts).astype(np.uint8)
    if len(args.e57) > 1:
        print(f"verschmolzen: {len(xyz):,} Punkte aus {len(args.e57)} Standpunkten")

    idx = voxel_idx(xyz, args.voxel)
    xyz, rgb = xyz[idx], rgb[idx]
    print(f"nach Voxel-Ausduennung ({args.voxel} m): {len(xyz):,}")

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(),
                       np.percentile(xyz[:, 2], 1)])
    local = (xyz - origin).astype(np.float32)   # z-up beibehalten

    dest = MEDIA / "scenes" / args.id
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        sel = (rng.choice(len(local), maxpts, replace=False)
               if len(local) > maxpts else np.arange(len(local)))
        p = np.ascontiguousarray(local[sel], "<f4")
        c = np.ascontiguousarray(rgb[sel], np.uint8)
        (dest / fname).write_bytes(p.tobytes() + c.tobytes())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{args.id}/{fname}",
                       "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        print(f"  {label}: {len(p):,} Punkte")
        if lid == "lite":
            W, H = 640, 480
            img = np.full((H, W, 3), 13, np.uint8)
            nx = ((p[:, 0] - p[:, 0].min()) / max(np.ptp(p[:, 0]), 1e-6) * (W - 1)).astype(int)
            ny = ((p[:, 2] - p[:, 2].min()) / max(np.ptp(p[:, 2]), 1e-6) * (H - 1)).astype(int)
            img[H - 1 - ny, nx] = c                       # Seitenansicht (x/z)
            Image.fromarray(img).save(dest / "thumb.jpg", quality=85)

    scene = {
        "id": args.id,
        "title": args.title or f"Renon — RGB-Punktwolke ({args.id})",
        "description": (
            f"Reale RGB-Punktwolke eines terrestrischen Scans (E57) am Renon-Standort "
            f"(ICOS IT-Ren), gemessene Farbe je Punkt. {len(xyz):,} Punkte nach "
            f"Ausduennung, begehbar. Weiterer Standpunkt neben renon-setup01 -- die "
            f"Scan-Schatten liegen anders, der Bestand wird von einer zweiten Position "
            f"sichtbar. Quelle: E57 (6 Pinhole-Kameras + Punktwolke), offener "
            f"Renon-Datensatz."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.id}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "e57", "origin_xyz": [float(c) for c in origin],
                   "dataset": "Renon (ICOS IT-Ren), terrestrischer Laserscan (E57)",
                   "gps": {"lat": 46.58686, "lon": 11.43369},
                   "coord_source": "ICOS-Station IT-Ren (Stationskoordinate, nicht Setup-genau)"},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{args.id}' gebaut ({len(xyz):,} Punkte)")


if __name__ == "__main__":
    main()
