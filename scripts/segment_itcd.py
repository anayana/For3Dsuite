#!/usr/bin/env python3
"""segment_itcd.py -- Punktwolke in Einzelbaeume segmentieren und einfaerben.

ITCD-Baseline (Individual Tree Crown Delineation) auf der fertigen Web-Wolke:
Jeder Punkt wird dem naechstgelegenen erkannten Stamm zugeordnet (Zuordnung in
XY, begrenzt durch einen BHD-abhaengigen Kronenradius). Bodenpunkte und Punkte
ohne Stamm in Reichweite bleiben grau. Ergebnis ist eine zweite .bin-Datei mit
identischen Positionen, aber baumweiser Einfaerbung -- der Viewer kann zwischen
"RGB" und "Einzelbaeume" umschalten, ohne die Geometrie neu zu laden.

Ehrliche Einordnung: reine Naechster-Stamm-Zuordnung (Voronoi-artig), kein
Region-Growing und keine Kronenmodellierung. In dichten, verzahnten Kronen
schneidet sie zwangslaeufig gerade Grenzen -- als Visualisierung und Baseline
gedacht, nicht als validierte Kronenabgrenzung.

Positionen und Staemme liegen im selben Frame (Bin = Welt - source.origin_xyz),
genau wie die Marker-Billboards im 3D-Viewer.

Nutzung:
  python segment_itcd.py <scene.json> [--media-dir DIR] [--max-radius 4.0]
"""
import argparse
import json
from pathlib import Path

import numpy as np

CELL_GROUND = 2.0    # m, Rasterweite des Bodenmodells
GROUND_PCT = 5       # Perzentil der z-Werte je Zelle = Boden
GROUND_H = 0.4       # m ueber Boden: darunter gilt als Boden (grau)
R_MIN, R_MAX = 1.5, 4.0   # m, Kronenradius-Grenzen
GREY = (110, 114, 120)

# Gut unterscheidbare Farben (zyklisch ueber die Baeume)
PALETTE = np.array([
    [230, 100, 90], [90, 200, 120], [95, 160, 240], [240, 190, 80],
    [200, 120, 230], [90, 210, 210], [240, 140, 60], [160, 210, 90],
    [240, 130, 180], [130, 140, 240], [80, 190, 160], [220, 220, 110],
], np.uint8)


def read_bin(path, count):
    """Blockformat aus pointcloud_web.py -> (xyz float32 (n,3), rgb uint8 (n,3))."""
    raw = np.fromfile(path, dtype=np.uint8)
    xyz = raw[: count * 12].view("<f4").reshape(count, 3)
    rgb = raw[count * 12: count * 12 + count * 3].reshape(count, 3)
    return xyz, rgb


def ground_height(xyz):
    """Grobes Bodenmodell -> Hoehe ueber Boden je Punkt."""
    ix = np.floor(xyz[:, 0] / CELL_GROUND).astype(np.int64)
    iy = np.floor(xyz[:, 1] / CELL_GROUND).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    gmap = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 5:
            gmap[ks[lo]] = float(np.percentile(zs[lo:hi], GROUND_PCT))
    if not gmap:
        return xyz[:, 2] - float(xyz[:, 2].min())
    default = float(np.median(list(gmap.values())))
    ground = np.array([gmap.get(k, default) for k in key], np.float32)
    return xyz[:, 2] - ground


def stems_from_scene(scene):
    """Stammpositionen im Bin-Frame + Kronenradius aus dem BHD."""
    origin = np.array((scene.get("source") or {}).get("origin_xyz") or [0, 0, 0], np.float32)
    pos, rad, ids = [], [], []
    for m in scene.get("markers", []):
        xyz = m.get("xyz")
        if not xyz:
            continue
        pos.append([xyz[0] - origin[0], xyz[1] - origin[1]])
        bhd = (m.get("attributes") or {}).get("BHD_cm") or 20.0
        rad.append(float(np.clip(0.6 + 0.06 * float(bhd), R_MIN, R_MAX)))
        ids.append(m.get("id"))
    return np.array(pos, np.float32), np.array(rad, np.float32), ids


def segment(xyz, stems, radii, max_radius):
    """Naechster-Stamm-Zuordnung in XY. -1 = Boden/keiner in Reichweite."""
    n = len(xyz)
    label = np.full(n, -1, np.int32)
    h = ground_height(xyz)
    cand = h > GROUND_H                      # Boden raus
    idx = np.flatnonzero(cand)
    if not len(idx) or not len(stems):
        return label, h
    for s in range(0, len(idx), 50_000):     # blockweise: Speicher begrenzen
        part = idx[s: s + 50_000]
        d = np.linalg.norm(xyz[part, None, :2] - stems[None, :, :], axis=2)
        near = np.argmin(d, axis=1)
        dmin = d[np.arange(len(part)), near]
        ok = dmin <= np.minimum(radii[near], max_radius)
        label[part[ok]] = near[ok]
    return label, h


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scene", help="scene.json (Marker = Staemme, source.origin_xyz)")
    ap.add_argument("--media-dir", help="Verzeichnis der .bin-Dateien "
                    "(Default: Ordner der scene.json)")
    ap.add_argument("--max-radius", type=float, default=R_MAX)
    args = ap.parse_args()

    spath = Path(args.scene)
    scene = json.loads(spath.read_text(encoding="utf-8"))
    media = Path(args.media_dir) if args.media_dir else spath.parent

    stems, radii, ids = stems_from_scene(scene)
    if not len(stems):
        raise SystemExit("Keine Marker mit xyz in der Szene -- nichts zu segmentieren")
    print(f"{len(stems)} Staemme, Kronenradius {radii.min():.1f}-{radii.max():.1f} m")

    pc = scene.get("pointcloud") or {}
    levels = pc.get("levels") or ([pc] if pc.get("bin") else [])
    if not levels:
        raise SystemExit("Szene hat keine pointcloud/levels")

    for lv in levels:
        name = Path(lv["bin"]).name
        src = media / name
        if not src.is_file():
            print(f"  {name}: nicht gefunden, uebersprungen")
            continue
        xyz, _ = read_bin(src, lv["count"])
        label, _ = segment(xyz, stems, radii, args.max_radius)

        rgb = np.empty((len(xyz), 3), np.uint8)
        rgb[:] = GREY
        hit = label >= 0
        rgb[hit] = PALETTE[label[hit] % len(PALETTE)]

        out = src.with_name(src.stem + "_seg.bin")
        out.write_bytes(xyz.astype("<f4").tobytes() + rgb.tobytes())
        meta = {"count": int(len(xyz)),
                "bbox_min": [float(c) for c in xyz.min(0)],
                "bbox_max": [float(c) for c in xyz.max(0)]}
        out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
        lv["bin_itcd"] = str(Path(lv["bin"]).parent / out.name).replace("\\", "/")

        share = 100.0 * hit.sum() / len(xyz)
        trees_hit = len(np.unique(label[hit]))
        print(f"  {name}: {hit.sum():,}/{len(xyz):,} Punkte zugeordnet ({share:.1f}%), "
              f"{trees_hit} Baeume getroffen -> {out.name}")

    spath.write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> bin_itcd je Stufe in {spath} eingetragen")


if __name__ == "__main__":
    main()
