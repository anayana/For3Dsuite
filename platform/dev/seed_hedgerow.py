#!/usr/bin/env python3
"""seed_hedgerow.py -- Belgische Heckenreihen (TLS) als Punktwolken-Szenen.

Quelle: Zenodo 4487116 (CC-BY-4.0), RIEGL VZ-1000, Einzelbaum-Punktwolken aus
Hecken und Baumreihen in der Agrarlandschaft Flanderns. Die Baeume behalten ihre
ko-registrierten Koordinaten, lassen sich also je Standort wieder zur realen
Reihe zusammensetzen.

Besonderheit gegenueber der ITCD-Segmentierung: die Baumzugehoerigkeit ist hier
GROUND TRUTH (je Baum eine Datei), nicht geschaetzt -- die Einfaerbung zeigt die
echte Zuordnung. Art folgt aus dem Quell-Archiv (Erle/Birke).

Kein Panorama und keine Mehrfach-Standpunkte: der Datensatz enthaelt nur die
extrahierten Baumwolken, keine Scanner-Bilder und keine Rohscans.

  python platform/dev/seed_hedgerow.py            # beide Standorte
  python platform/dev/seed_hedgerow.py M          # nur Standort M
"""
import json
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
SRC = REPO / "data" / "hedgerow_be"
sys.path.insert(0, str(REPO / "scripts"))
from inventory_from_cloud import fit_circle                      # noqa: E402

ARCHIVES = {"Alder_Tree point clouds TXT.zip": "Erle",
            "Betula_Tree point clouds TXT.zip": "Birke"}
SITES = {"M": ("hedgerow-be-alder", "Heckenreihe Flandern — Erlen (Standort M)"),
         "T": ("hedgerow-be-birch", "Heckenreihe Flandern — Birken (Standort T)")}
LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]
PALETTE = np.array([
    [230, 100, 90], [90, 200, 120], [95, 160, 240], [240, 190, 80],
    [200, 120, 230], [90, 210, 210], [240, 140, 60], [160, 210, 90],
    [240, 130, 180], [130, 140, 240], [80, 190, 160], [220, 220, 110],
], np.uint8)


def load_trees():
    """{standort: [(name, art, punkte), ...]} aus den Zenodo-Archiven."""
    sites = {}
    for arc, art in ARCHIVES.items():
        zf = zipfile.ZipFile(SRC / arc)
        for n in zf.namelist():
            if not n.lower().endswith(".txt"):
                continue
            stem = n.split("/")[-1][:-4]
            with zf.open(n) as fh:
                pts = np.loadtxt(fh, dtype=np.float32)
            sites.setdefault(stem.split("_")[0], []).append((stem, art, pts))
    return sites


def tree_metrics(pts):
    """Hoehe ueber Stammfuss und BHD aus dem Brusthoehen-Ring (Kasa-Fit)."""
    base = float(np.percentile(pts[:, 2], 1))
    height = float(pts[:, 2].max() - base)
    sl = pts[(pts[:, 2] - base >= 1.0) & (pts[:, 2] - base <= 1.6)]
    bhd = None
    if len(sl) >= 30:
        fit = fit_circle(sl[:, 0].astype(float), sl[:, 1].astype(float))
        if fit:
            cx, cy, r, rms, arc = fit
            if 0.02 <= r <= 0.8 and rms <= 0.05:
                bhd = round(2 * r * 100, 1)
    xy = sl[:, :2].mean(0) if len(sl) else pts[:, :2].mean(0)
    return float(xy[0]), float(xy[1]), base, height, bhd


def write_bin(path, xyz, rgb, origin):
    xyz = (xyz - origin).astype("<f4")
    path.write_bytes(xyz.tobytes() + rgb.astype(np.uint8).tobytes())
    path.with_suffix(".json").write_text(json.dumps({
        "count": int(len(xyz)),
        "origin_xyz": [float(c) for c in origin],
        "bbox_min": [float(c) for c in xyz.min(0)],
        "bbox_max": [float(c) for c in xyz.max(0)]}, indent=2))


def thumbnail(dest, xyz, rgb):
    W, H = 640, 320
    img = np.full((H, W, 3), 13, np.uint8)
    x, y = xyz[:, 0], xyz[:, 1]
    nx = ((x - x.min()) / max(np.ptp(x), 1e-6) * (W - 1)).astype(int)
    ny = ((y - y.min()) / max(np.ptp(y), 1e-6) * (H - 1)).astype(int)
    img[H - 1 - ny, nx] = rgb
    Image.fromarray(img).save(dest, quality=85)


def build(site, trees):
    sid, title = SITES[site]
    dest = MEDIA / "scenes" / sid
    dest.mkdir(parents=True, exist_ok=True)

    xyz = np.concatenate([t[2] for t in trees])
    rgb = np.concatenate([np.broadcast_to(PALETTE[i % len(PALETTE)], (len(t[2]), 3))
                          for i, t in enumerate(trees)])
    origin = xyz.mean(0)

    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        idx = (rng.choice(len(xyz), maxpts, replace=False)
               if len(xyz) > maxpts else np.arange(len(xyz)))
        write_bin(dest / fname, xyz[idx], rgb[idx], origin)
        mj = json.loads((dest / fname).with_suffix(".json").read_text())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{sid}/{fname}",
                       "count": mj["count"], "bbox_min": mj["bbox_min"],
                       "bbox_max": mj["bbox_max"]})
        if lid == "lite":
            thumbnail(dest / "thumb.jpg", xyz[idx] - origin, rgb[idx])

    markers, arten = [], {}
    for i, (name, art, pts) in enumerate(trees, 1):
        x, y, base, height, bhd = tree_metrics(pts)
        arten[art] = arten.get(art, 0) + 1
        attrs = {"Art": art, "Hoehe_m": round(height, 1), "Punkte": int(len(pts))}
        if bhd:
            attrs["BHD_cm"] = bhd
        dx, dy, dz = x - origin[0], y - origin[1], (base + 1.3) - origin[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        markers.append({
            "id": f"t{i:03d}", "label": f"{art} {name}",
            "yaw": round(math.degrees(math.atan2(dy, dx)), 3),
            "pitch": round(math.degrees(math.asin(dz / dist)), 3),
            "xyz": [round(x, 3), round(y, 3), round(base + 1.3, 3)],
            "attributes": attrs, "demo": False})

    n_bhd = sum(1 for m in markers if "BHD_cm" in m["attributes"])
    scene = {
        "id": sid, "title": title,
        "description": (f"Terrestrischer Laserscan (RIEGL VZ-1000) von Baeumen aus "
                        f"Hecken und Baumreihen der Agrarlandschaft Flanderns. "
                        f"{len(trees)} Baeume ({', '.join(f'{n}x {a}' for a, n in arten.items())}) "
                        f"in ihrer ko-registrierten Lage; Einfaerbung = echte "
                        f"Baumzugehoerigkeit aus dem Datensatz (Ground Truth, keine "
                        f"Segmentierung). Kein Panorama im Datensatz enthalten. "
                        f"Quelle: Zenodo 4487116, CC-BY-4.0."),
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{sid}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {"type": "hedgerow-tls", "origin_xyz": [float(c) for c in origin],
                   "dataset": "Belgian hedgerows and tree rows (RIEGL VZ-1000)",
                   "url": "https://zenodo.org/records/4487116", "license": "CC-BY-4.0"},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "levels": levels},
        "markers": markers,
    }
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"  Szene '{sid}': {len(trees)} Baeume, {len(xyz):,} Punkte "
          f"(Stufen {levels[0]['count']:,}/{levels[1]['count']:,}), BHD fuer {n_bhd}")


def main():
    want = sys.argv[1:] or list(SITES)
    sites = load_trees()
    for site in want:
        if site not in sites:
            print(f"  Standort {site} nicht in den Daten"); continue
        build(site, sorted(sites[site]))


if __name__ == "__main__":
    main()
