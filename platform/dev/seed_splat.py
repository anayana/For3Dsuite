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
    ap.add_argument("--camera-up", nargs=3, type=float, default=None,
                    help="Up-Achse manuell; ohne Angabe automatisch aus der Bodenebene (PCA)")
    ap.add_argument("--note", default="Trainiertes 3DGS (Neuansichts-Synthese).")
    ap.add_argument("--external-url",
                    help="Splat-.ply extern hosten (z. B. GitHub-Release): URL statt "
                    "Kopie ins Repo. Die .ply wird nur fuer bbox/Up/Thumbnail gelesen.")
    args = ap.parse_args()

    arr, names = read_ply(args.ply)
    xyz = np.stack([arr["x"], arr["y"], arr["z"]], 1).astype(np.float32)

    # Up-Achse: manuell, sonst aus der Bodenebene schaetzen (PCA-Normale).
    # 3DGS/COLMAP-Szenen sind beliebig orientiert -> ein festes [0,-1,0] kippt.
    if args.camera_up is None:
        cen = xyz.mean(0)
        _, V = np.linalg.eigh(np.cov((xyz - cen).T))
        up = V[:, 0]                                   # kleinster Eigenwert = Ebenennormale
        proj = (xyz - cen) @ up                        # Vorzeichen: Tail (Baeume) = oben
        if proj.mean() < np.median(proj):
            up = -up
        args.camera_up = [float(c) for c in up]
        print(f"  Up-Achse automatisch (Bodenebene): "
              f"[{up[0]:.2f}, {up[1]:.2f}, {up[2]:.2f}]")
    fdc = np.stack([arr.get(f"f_dc_{i}") if hasattr(arr, "get") else arr[f"f_dc_{i}"]
                    for i in range(3)], 1)
    col = np.clip(0.5 + C0 * fdc, 0, 1)
    col = (col * 255).astype(np.uint8)
    # robuste bbox (2..98 %) -> ignoriert Rest-Ausreisser bei der Kamera
    lo = np.percentile(xyz, 2, 0); hi = np.percentile(xyz, 98, 0)
    focus = np.median(xyz, 0)                       # dichter Kern (~Stumpf) = Blickziel

    dest = MEDIA / "scenes" / args.id
    dest.mkdir(parents=True, exist_ok=True)
    thumbnail(xyz, col, args.camera_up, dest / "thumb.jpg")

    splat = {"camera_up": args.camera_up,
             "bbox": {"bbox_min": lo.tolist(), "bbox_max": hi.tolist()},
             "focus": focus.tolist(),
             "note": args.note}
    if args.external_url:                          # extern gehostet (Release/CDN)
        splat["url"] = args.external_url
    else:                                          # ins Repo kopieren (kleine Dateien)
        shutil.copyfile(args.ply, dest / "model.ply")
        splat["file"] = "model.ply"

    scene = {
        "id": args.id, "title": args.title, "description": args.description,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.id}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "3dgs"},
        "splat": splat,
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    mb = Path(args.ply).stat().st_size / 1e6
    where = f"extern: {args.external_url}" if args.external_url else "im Repo (docs)"
    print(f"Szene '{args.id}': {len(xyz):,} Gaussians, {mb:.1f} MB ({where})")


if __name__ == "__main__":
    main()
