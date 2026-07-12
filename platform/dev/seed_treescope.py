#!/usr/bin/env python3
"""seed_treescope.py -- TreeScope-Kachel als reine Punktwolken-Szene einspielen.

Baut aus data/Treescope/cloud1_0 eine wolken-only-Szene (kein Panorama):
  1. Inventur (inventory_from_cloud.py) -> berechnete Staemme (BHD, Grundflaeche)
  2. Validierung gegen die Instanz-Labels (Recall/Precision/Lagefehler)
  3. Web-Punktwolke in zwei Dichte-Stufen (hoehen-eingefaerbt, da kein RGB)
  4. Marker aus den berechneten Werten; Validierungskennzahlen ins Manifest
  5. Top-down-Thumbnail

  python platform/dev/seed_treescope.py
"""
import csv
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
TS = REPO / "data" / "Treescope"
sys.path.insert(0, str(SCRIPTS))
from pcd_io import read_pcd, read_labels          # noqa: E402
from pano_variants import make_variants           # noqa: E402  (nicht genutzt, Konsistenz)
import validate_treescope as vts                  # noqa: E402
import markers_from_xyz as mfx                     # noqa: E402

SID = "treescope-wsf19"
TILE = "cloud1_0"


def run_inventory():
    csv_out = TS / f"{TILE}_trees.csv"
    subprocess.run([sys.executable, str(SCRIPTS / "inventory_from_cloud.py"),
                    str(TS / f"{TILE}_all_points.pcd"), str(csv_out),
                    "--min-points", "15", "--arc-min", "50", "--rms-max", "5",
                    "--nms-dist", "0.5", "--bh", "0.5", "2.5", "--min-tree-height", "5"],
                   check=True)
    return csv_out


def validate(csv_out):
    x, y, z, _ = read_pcd(str(TS / f"{TILE}_all_points.pcd"))
    lab = read_labels(str(TS / f"{TILE}_all_points.labels"))
    gt = vts.gt_tree_positions(x, y, z, lab, 20)
    det = vts.load_detected(str(csv_out))
    matches, gt_used, det_used = vts.match(gt, det, 0.5)
    tp = len(matches)
    recall = tp / len(gt) if gt else 0
    precision = tp / len(det) if det else 0
    errs = [d for _, _, d in matches]
    return {
        "reference_trees": len(gt), "detected": len(det), "matched": tp,
        "recall": round(recall, 3), "precision": round(precision, 3),
        "f1": round(2 * recall * precision / (recall + precision), 3) if (recall + precision) else 0,
        "pos_err_median_cm": round(float(np.median(errs)) * 100, 1) if errs else None,
        "match_dist_m": 0.5,
        "method": "inventory_from_cloud.py (numpy Kreis-Fit) vs. TreeScope-Instanz-Labels",
    }


def thumbnail(dest):
    x, y, z, _ = read_pcd(str(TS / f"{TILE}_all_points.pcd"))
    W, H = 640, 320
    img = np.full((H, W, 3), 13, np.uint8)
    nx = ((x - x.min()) / (x.max() - x.min()) * (W - 1)).astype(int)
    ny = ((y - y.min()) / (y.max() - y.min()) * (H - 1)).astype(int)
    t = np.clip((z - np.percentile(z, 2)) / (np.percentile(z, 98) - np.percentile(z, 2)), 0, 1)
    col = np.stack([30 + t * 220, 45 + t * 205, 90 + t * 60], -1).astype(np.uint8)
    img[H - 1 - ny, nx] = col
    Image.fromarray(img).save(dest, quality=85)


def main():
    dest = MEDIA / "scenes" / SID
    dest.mkdir(parents=True, exist_ok=True)

    csv_out = run_inventory()
    metrics = validate(csv_out)
    print(f"Validierung: Recall {metrics['recall']:.0%}, Precision {metrics['precision']:.0%}, "
          f"Lagefehler {metrics['pos_err_median_cm']} cm (n={metrics['reference_trees']} GT)")

    # Web-Wolken (hoehen-eingefaerbt) in zwei Stufen
    for fname, voxel, maxpts in (("cloud_lite.bin", "0.08", "160000"),
                                 ("cloud.bin", "0.02", "700000")):
        subprocess.run([sys.executable, str(SCRIPTS / "pointcloud_web.py"),
                        str(TS / f"{TILE}_all_points.pcd"), str(dest / fname),
                        "--voxel", voxel, "--max-points", maxpts, "--color-by-height"],
                       check=True)
    meta = json.loads((dest / "cloud.json").read_text())
    origin = meta["origin_xyz"]
    levels = []
    for lid, label, fname in (("lite", "Ausgedünnt", "cloud_lite.bin"),
                              ("full", "Voll", "cloud.bin")):
        mj = json.loads((dest / Path(fname).with_suffix(".json").name).read_text())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{SID}/{fname}",
                       "count": mj["count"], "bbox_min": mj["bbox_min"], "bbox_max": mj["bbox_max"]})
    pointcloud = {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                  "levels": levels}

    # Marker aus den berechneten Werten (Ursprung = Wolken-Zentroid, damit die
    # 3D-Sprites mit der zentrierten Web-Wolke zusammenfallen)
    with open(csv_out, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    markers = [mfx.to_marker(dict(r), origin, i + 1) for i, r in enumerate(rows)]

    thumbnail(dest / "thumb.jpg")

    scene = {
        "id": SID,
        "title": "TreeScope WSF-19 — Mobile-Laserscan (Kachel 0)",
        "description": "Mobiler Wald-Laserscan (TreeScope, tnl.treescope.org). Reine "
                       "Punktwolke ohne Bilder; Marker = automatisch aus der Wolke "
                       "berechnete Einzelbaeume (BHD, Grundflaeche), validiert gegen die "
                       "Instanz-Labels des Datensatzes. Hoehe hier gekappt (Low-Scan).",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{SID}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "treescope", "origin_xyz": origin,
                   "dataset": "TreeScope v1.0 WSF-19", "url": "https://tnl.treescope.org"},
        "pointcloud": pointcloud,
        "validation": metrics,
        "markers": markers,
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"Szene '{SID}' veroeffentlicht ({len(markers)} berechnete Baeume, "
          f"{pointcloud['count']} Punkte Default-Stufe)")


if __name__ == "__main__":
    main()
