#!/usr/bin/env python3
"""seed_splat.py -- eine trainierte 3DGS-.ply als begehbare RGB-Splat-Szene einhaengen.

Nimmt ein 3D-Gaussian-Splatting-Ergebnis (INRIA-.ply, z. B. aus train_mipnerf.sh)
und macht daraus eine Szene vom Typ "splat" -- fotorealistisch, begehbar ueber
splat.html. Optional vorher mit scripts/clean_splat.py die Hintergrund-Fetzen
entfernen.

  python platform/dev/seed_splat.py stump_gaussians.ply --id stump-3dgs \
      --title "Mip-NeRF Stumpf (3DGS)" --description "..." [--camera-up 0 -1 0]
"""
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
sys.path.insert(0, str(REPO / "scripts"))
from clean_splat import read_ply                      # noqa: E402

C0 = 0.28209479177387814


def thumbnail(xyz, col, up, dest):
    """Draufsicht entlang der Up-Achse."""
    up = np.array(up, float); up /= np.linalg.norm(up)
    ref = np.array([0, 0, 1.]) if abs(up[2]) < 0.9 else np.array([1., 0, 0])
    a = np.cross(ref, up); a /= np.linalg.norm(a)
    b = np.cross(up, a)
    u, v = xyz @ a, xyz @ b
    W, H = 640, 320
    img = np.zeros((H, W, 3), np.uint8)
    nx = ((u - u.min()) / max(np.ptp(u), 1e-6) * (W - 1)).astype(int)
    ny = ((v - v.min()) / max(np.ptp(v), 1e-6) * (H - 1)).astype(int)
    order = np.argsort(xyz @ up)                       # hintere zuerst
    img[H - 1 - ny[order], nx[order]] = col[order]
    Image.fromarray(img).save(dest, quality=85)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("ply")
    ap.add_argument("--id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", default="Begehbares 3D-Gaussian-Splatting-Ergebnis.")
    ap.add_argument("--camera-up", nargs=3, type=float, default=[0, -1, 0],
                    help="Up-Achse (3DGS-Standard 0 -1 0)")
    ap.add_argument("--note", default="Trainiertes 3DGS (Neuansichts-Synthese).")
    args = ap.parse_args()

    arr, names = read_ply(args.ply)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1).astype(np.float32)
    fdc = np.stack([arr.get(f"f_dc_{i}") if hasattr(arr, "get") else arr[f"f_dc_{i}"]
                    for i in range(3)], 1)
    col = np.clip(0.5 + C0 * fdc, 0, 1)
    col = (col * 255).astype(np.uint8)
    # robuste bbox (2..98 %) -> ignoriert Rest-Ausreisser bei der Kamera
    lo = np.percentile(xyz, 2, 0); hi = np.percentile(xyz, 98, 0)

    dest = MEDIA / "scenes" / args.id
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(args.ply, dest / "model.ply")
    thumbnail(xyz, col, args.camera_up, dest / "thumb.jpg")

    scene = {
        "id": args.id, "title": args.title, "description": args.description,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.id}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "3dgs"},
        "splat": {
            "file": "model.ply",
            "camera_up": args.camera_up,
            "bbox": {"bbox_min": lo.tolist(), "bbox_max": hi.tolist()},
            "note": args.note,
        },
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    mb = (dest / "model.ply").stat().st_size / 1e6
    print(f"Szene '{args.id}': {len(xyz):,} Gaussians, {mb:.1f} MB")
    print(f"  -> publish.json ergaenzen + export_static.py laufen lassen")


if __name__ == "__main__":
    main()
