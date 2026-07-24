#!/usr/bin/env python3
"""seed_splat_demo.py -- Demo-Splat-Szene aus einer vorhandenen Punktwolke.

Baut eine Szene vom Typ "splat": die Renon-Web-Wolke wird per points_to_splat.py
zu einer 3DGS-.ply gemacht und ueber splat.html gerendert. So laesst sich der
Splat-Viewer mit echten Daten testen, bevor ein trainiertes 3DGS-Ergebnis
vorliegt. Ehrlich als Platzhalter gekennzeichnet (Punktwolke als Gaussians,
KEINE Neuansichts-Synthese).

Ein trainiertes Ergebnis (z. B. stump_gaussians.ply aus train_mipnerf.sh) wird
spaeter genauso eingehaengt -- nur die .ply austauschen und splat.note anpassen.

  python platform/dev/seed_splat_demo.py
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
SCRIPTS = REPO / "scripts"
SRC_SCENE = MEDIA / "scenes" / "renon-setup01"
SID = "renon-splat-demo"


def thumbnail(bin_path, count, dest):
    raw = np.fromfile(bin_path, dtype=np.uint8)
    xyz = raw[: count * 12].view("<f4").reshape(count, 3)
    rgb = raw[count * 12: count * 12 + count * 3].reshape(count, 3)
    W, H = 640, 320
    img = np.zeros((H, W, 3), np.uint8)
    nx = ((xyz[:, 0] - xyz[:, 0].min()) / max(np.ptp(xyz[:, 0]), 1e-6) * (W - 1)).astype(int)
    ny = ((xyz[:, 2] - xyz[:, 2].min()) / max(np.ptp(xyz[:, 2]), 1e-6) * (H - 1)).astype(int)
    img[H - 1 - ny, nx] = rgb
    Image.fromarray(img).save(dest, quality=85)


def main():
    dest = MEDIA / "scenes" / SID
    dest.mkdir(parents=True, exist_ok=True)
    src_bin = SRC_SCENE / "cloud.bin"
    meta = json.loads((SRC_SCENE / "cloud.json").read_text())
    count = meta["count"]

    ply = dest / "renon_splat.ply"
    subprocess.run([sys.executable, str(SCRIPTS / "points_to_splat.py"),
                    str(src_bin), str(ply), "--count", str(count),
                    "--max", "150000", "--size", "0.05"], check=True)
    thumbnail(src_bin, count, dest / "thumb.jpg")

    scene = {
        "id": SID,
        "title": "Renon — Splat-Demo (Punktwolke als Gaussians)",
        "description": ("Platzhalter zum Testen des Gaussian-Splat-Viewers: die "
                        "Renon-LiDAR-Wolke als opake Gaussians gerendert. KEINE "
                        "trainierte Neuansichts-Synthese -- ein echtes 3DGS-Ergebnis "
                        "(dichte Mehransichts-Aufnahme) faellt hier spaeter genauso rein."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{SID}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "splat-demo", "note": "aus renon-setup01/cloud.bin"},
        "splat": {
            "file": "renon_splat.ply",
            "camera_up": [0, 0, 1],                 # Wolke ist z-oben
            "bbox": {"bbox_min": meta["bbox_min"], "bbox_max": meta["bbox_max"]},
            "note": "Punktwolke als Gaussians (Platzhalter) — kein trainiertes 3DGS.",
        },
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    mb = ply.stat().st_size / 1e6
    print(f"Szene '{SID}' veroeffentlicht ({mb:.1f} MB Splat-PLY)")


if __name__ == "__main__":
    main()
