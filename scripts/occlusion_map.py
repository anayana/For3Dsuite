#!/usr/bin/env python3
"""occlusion_map.py -- Verdeckungs-/Sichtbarkeitskarte einer Mehr-Standpunkt-TLS-Wolke.

Setzt das CANOPy-Konzept (Verdeckungsanalyse, GeoSense Freiburg) im Geist der
Suite um: welche Teile eines Bestands sind gut sichtbar und welche durch Baeume
verdeckt? Der Ansatz nutzt die MEHREREN Standpunkte eines HELIOS++-Laufs (jede
leg*_points.xyz = ein Scanner): ein Punkt/Voxel, der aus vielen Standpunkten
Returns bekommt, ist gut beobachtet; einer aus nur einem Standpunkt ist
verdeckungsgefaehrdet (einseitig gesehen). Am synthetischen Scan ist das der
saubere Testfall -- die Scanner-Positionen und die Wahrheit sind bekannt.

Das ist der geometrische Kern der Verdeckungsdiagnose (Exposé-Grenze
"Einzelscan-Verdeckung"): sie macht sichtbar, wo eine Einzelscan-Inventur blind ist.

  python scripts/occlusion_map.py <helios-output-dir> [--id renon-occlusion]
      [--voxel 0.15]
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


def vkeys(xyz, voxel):
    """Ganzzahliger Voxel-Hash je Punkt (kollisionsarm)."""
    k = np.floor(xyz / voxel).astype(np.int64)
    return (k[:, 0] * 73856093) ^ (k[:, 1] * 19349663) ^ (k[:, 2] * 83492791)


def vis_ramp(t):
    """1 Standpunkt (verdeckt) rot -> viele (frei sichtbar) gruen."""
    t = np.clip(t, 0, 1)
    stops = np.array([[210, 60, 50], [235, 150, 60], [230, 215, 90],
                      [120, 190, 90], [40, 150, 95]], np.float32)
    pos = np.linspace(0, 1, len(stops))
    return np.stack([np.interp(t, pos, stops[:, k]) for k in range(3)], -1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--id", default="renon-occlusion")
    ap.add_argument("--voxel", type=float, default=0.15)
    args = ap.parse_args()

    legs = sorted(glob.glob(os.path.join(args.outdir, "**", "leg*_points.xyz"),
                            recursive=True))
    if len(legs) < 2:
        raise SystemExit(f"mindestens 2 Standpunkte noetig, {len(legs)} gefunden")
    nlegs = len(legs)
    print(f"{nlegs} Standpunkte")

    # Je Standpunkt die Menge belegter Voxel; parallel alle Punkte sammeln
    seen_sets, allpts = [], []
    for l in legs:
        a = np.loadtxt(l, usecols=(0, 1, 2), dtype=np.float64)
        allpts.append(a)
        seen_sets.append(np.unique(vkeys(a, args.voxel)))
        print(f"  {os.path.basename(l)}: {len(a):,}")
    xyz = np.concatenate(allpts)

    # Ausduennen (ein Punkt je Voxel) fuer die Web-Wolke
    mk = vkeys(xyz, args.voxel)
    _, uidx = np.unique(mk, return_index=True)
    xyz, mk = xyz[uidx], mk[uidx]

    # Sichtbarkeit = aus wie vielen Standpunkten dieses Voxel Returns bekam
    vis = np.zeros(len(xyz), np.int32)
    for s in seen_sets:
        vis += np.isin(mk, s, assume_unique=False)
    frac = (vis - 1) / max(nlegs - 1, 1)              # 0 = nur 1 Sicht, 1 = alle
    print(f"Sichtbarkeit: median {np.median(vis):.1f} Standpunkte; "
          f"nur 1 Sicht (verdeckungsgefaehrdet): {100*(vis<=1).mean():.0f}%")

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(),
                       np.percentile(xyz[:, 2], 1)])
    rgb_full = vis_ramp(frac)
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
        if lid == "lite":
            W = H = 640
            img = np.full((H, W, 3), 13, np.uint8)
            nx = ((p[:, 0] - p[:, 0].min()) / max(np.ptp(p[:, 0]), 1e-6) * (W - 1)).astype(int)
            ny = ((p[:, 1] - p[:, 1].min()) / max(np.ptp(p[:, 1]), 1e-6) * (H - 1)).astype(int)
            img[H - 1 - ny, nx] = c
            Image.fromarray(img).save(dest / "thumb.jpg", quality=85)

    scene = {
        "id": args.id,
        "title": "Renon — Verdeckungskarte (Sichtbarkeit je Standpunkt)",
        "description": (
            f"Verdeckungs-/Sichtbarkeitsanalyse (CANOPy-Konzept, GeoSense Freiburg) "
            f"auf dem synthetischen HELIOS++-Scan der Renon-Inventur, {nlegs} "
            f"TLS-Standpunkte. Eingefaerbt nach der Zahl der Standpunkte, aus denen "
            f"ein Punkt Returns bekam: ROT = nur von EINEM Standpunkt gesehen "
            f"(einseitig, verdeckungsgefaehrdet), GRUEN = von mehreren frei sichtbar. "
            f"So wird sichtbar, wo eine Einzelscan-Inventur blind ist -- der "
            f"geometrische Kern der Exposé-Grenze 'Einzelscan-Verdeckung'. Am "
            f"synthetischen Scan ist es der saubere Testfall (Standpunkte und Wahrheit "
            f"bekannt). CANOPy selbst ist (noch) nicht oeffentlich; hier das Konzept "
            f"im Geist der Suite umgesetzt (scripts/occlusion_map.py)."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.id}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "occlusion-analysis",
                   "origin_xyz": [float(c) for c in origin],
                   "dataset": "Verdeckungskarte des synthetischen HELIOS++-Scans",
                   "gps": {"lat": 46.58686, "lon": 11.43369}},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": [],
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{args.id}' gebaut ({len(xyz):,} Punkte, {nlegs} Standpunkte)")


if __name__ == "__main__":
    main()
