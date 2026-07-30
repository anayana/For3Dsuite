#!/usr/bin/env python3
"""seed_segforests.py -- SegmentedForests-Plots als begehbare Suite-Szenen.

Baut aus einer Analyse-Wolke (scripts/laz_analysis.py) die Web-Stufen der Suite
und legt NEBEN die gemessene Farbe die manuell annotierte Semantik als zweite
Einfaerbung. Der Viewer schaltet dann zwischen

    RGB  |  Ground Truth  |  Einzelbaeume (unsere ITCD)

um -- gemessen, annotiert, gerechnet direkt nebeneinander. Genau das fehlte allen
bisherigen Szenen: eine Wahrheit, an der sich die eigene Rechnung pruefen laesst.

  python platform/dev/seed_segforests.py plot_06 \\
      data/segforests/plot_06_analysis.npz data/segforests/classes.json \\
      --title "..." --description "..."
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]

# Farben je semantischer Klasse. Boden gedaempft, Stamm kraeftig, Nicht-Vegetation
# rot -- die Klassen, die als Fehldetektion in Frage kommen, sollen auffallen.
CLASS_COLORS = {
    0: (120, 170, 90),    1: (105, 95, 80),     2: (70, 150, 95),
    3: (215, 130, 60),    4: (150, 120, 70),    5: (95, 175, 150),
    6: (230, 70, 70),     7: (245, 60, 120),    8: (255, 120, 40),
    9: (230, 70, 70),     12: (120, 195, 120),  13: (200, 200, 110),
}
GREY = (140, 140, 140)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sid")
    ap.add_argument("cloud")
    ap.add_argument("classes")
    ap.add_argument("--title", required=True)
    ap.add_argument("--description", required=True)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--plot-info", default="", help="Zusatz fuer source.dataset")
    args = ap.parse_args()

    d = np.load(args.cloud)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    rgb = d["rgb"]
    cls = d["cls"]
    spec = json.loads(Path(args.classes).read_text(encoding="utf-8"))
    names = {int(k): v for k, v in spec["names"].items()}
    print(f"{len(xyz):,} Punkte, {len(np.unique(cls))} Klassen")

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(),
                       np.percentile(xyz[:, 2], 1)])
    local = (xyz - origin).astype(np.float32)

    dest = MEDIA / "scenes" / args.sid
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        sel = (rng.choice(len(local), maxpts, replace=False)
               if len(local) > maxpts else np.arange(len(local)))
        p = np.ascontiguousarray(local[sel], "<f4")
        c = np.ascontiguousarray(rgb[sel], np.uint8)
        (dest / fname).write_bytes(p.tobytes() + c.tobytes())

        # Zweite Einfaerbung: dieselbe Geometrie, Farbe = annotierte Klasse
        gt = np.empty((len(sel), 3), np.uint8)
        gt[:] = GREY
        cs = cls[sel]
        for code, col in CLASS_COLORS.items():
            gt[cs == code] = col
        gtname = fname.replace(".bin", "_gt.bin")
        (dest / gtname).write_bytes(p.tobytes() + gt.tobytes())

        levels.append({"id": lid, "label": label, "bin": f"scenes/{args.sid}/{fname}",
                       "bin_gt": f"scenes/{args.sid}/{gtname}",
                       "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        print(f"  {label}: {len(p):,} Punkte (+ Ground-Truth-Einfaerbung)")
        if lid == "lite":
            W, H = 640, 480
            img = np.full((H, W, 3), 13, np.uint8)
            nx = ((p[:, 0] - p[:, 0].min()) / max(np.ptp(p[:, 0]), 1e-6) * (W - 1)).astype(int)
            ny = ((p[:, 2] - p[:, 2].min()) / max(np.ptp(p[:, 2]), 1e-6) * (H - 1)).astype(int)
            img[H - 1 - ny, nx] = c
            Image.fromarray(img).save(dest / "thumb.jpg", quality=85)

    present = [int(v) for v in np.unique(cls)]
    scene = {
        "id": args.sid, "title": args.title, "description": args.description,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.sid}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {
            "type": "segmentedforests-tls",
            "origin_xyz": [float(c) for c in origin],
            "dataset": ("SegmentedForests -- manuell semantisch gelabelte TLS/MLS-"
                        "Waldwolken. " + args.plot_info),
            "url": "https://doi.org/10.5281/zenodo.17396681",
            "paper": "https://doi.org/10.1093/forestry/cpaf062",
            "license": "MIT",
        },
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "legend": {
            "title": "Semantische Ground Truth",
            "subtitle": "manuell annotiert, Feld 'Class' im LAZ",
            "items": [{"label": names.get(c, str(c)),
                       "color": "rgb({},{},{})".format(*CLASS_COLORS.get(c, GREY))}
                      for c in present],
            "note": ("Die Zuordnung Zahl -> Klassenname ist ABGELEITET: der "
                     "Datensatz liefert nur Zahlen, der Aufsatz nur eine Abbildung. "
                     "Herleitung und Sicherheit je Klasse in data/segforests/"
                     "classes.json."),
        },
        "markers": [],
    }
    if args.lat is not None:
        scene["source"]["gps"] = {"lat": args.lat, "lon": args.lon}
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{args.sid}' gebaut")


if __name__ == "__main__":
    main()
