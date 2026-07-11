#!/usr/bin/env python3
"""markers_from_xyz.py -- Inventurpositionen (XYZ) -> Panorama-Marker (Yaw/Pitch).

Rechnet Punktwolken-Koordinaten (z. B. Baumpositionen aus lidR/TreeLS/3DFin)
relativ zum Scan-Ursprung in Pannellum-Blickwinkel um. Der Ursprung ist die
Kamera-Translation aus der E57-Pose (scene.json -> source.origin_xyz).

Konvention passend zu reproject_pano.py (--sx 1 --sy -1, Welt z = oben):
  yaw   = atan2(dy, dx)      [Grad, 0 = +X-Achse des Scanner-KS]
  pitch = asin(dz / |d|)     [Grad]

CSV-Eingabe mit Header; Pflichtspalten x,y,z; optional label; alle weiteren
Spalten werden zu Marker-Attributen.

Nutzung:
  python markers_from_xyz.py trees.csv --origin 31.80 -4.56 3.86
  python markers_from_xyz.py trees.csv --scene pfad/zu/scene.json   # schreibt Marker hinein
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path


def to_marker(row, origin, idx):
    dx = float(row.pop("x")) - origin[0]
    dy = float(row.pop("y")) - origin[1]
    dz = float(row.pop("z")) - origin[2]
    dist = math.sqrt(dx * dx + dy * dy + dz * dz)
    if dist < 1e-6:
        raise ValueError("Punkt liegt im Scan-Ursprung")
    label = row.pop("label", "") or f"Objekt {idx}"
    attrs = {}
    for k, v in row.items():
        if v is None or v == "":
            continue
        try:
            attrs[k] = float(v)
        except ValueError:
            attrs[k] = v
    attrs.setdefault("Distanz_m", round(dist, 2))
    return {
        "id": f"t{idx:03d}",
        "label": label,
        "yaw": round(math.degrees(math.atan2(dy, dx)), 3),
        "pitch": round(math.degrees(math.asin(dz / dist)), 3),
        "xyz": [round(float(c), 3) for c in (dx + origin[0], dy + origin[1], dz + origin[2])],
        "attributes": attrs,
        "demo": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", help="CSV mit Spalten x,y,z[,label,weitere...]")
    ap.add_argument("--origin", nargs=3, type=float, metavar=("X", "Y", "Z"),
                    help="Scan-Ursprung; entfaellt bei --scene")
    ap.add_argument("--scene", help="scene.json: Ursprung daraus lesen und Marker hineinschreiben")
    ap.add_argument("--out", help="Marker stattdessen als JSON-Datei schreiben")
    args = ap.parse_args()

    scene = None
    if args.scene:
        scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
        origin = (scene.get("source") or {}).get("origin_xyz")
        if not origin:
            sys.exit("scene.json enthaelt kein source.origin_xyz — --origin angeben")
    elif args.origin:
        origin = args.origin
    else:
        sys.exit("Entweder --origin X Y Z oder --scene <scene.json> angeben")

    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"x", "y", "z"} <= set(rows[0]):
        sys.exit("CSV braucht eine Header-Zeile mit mindestens x,y,z")

    markers = [to_marker(dict(r), origin, i + 1) for i, r in enumerate(rows)]
    print(f"{len(markers)} Marker berechnet (Ursprung {origin})")

    if scene is not None:
        scene["markers"] = markers
        Path(args.scene).write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
        print(f"-> in {args.scene} geschrieben")
    elif args.out:
        Path(args.out).write_text(json.dumps(markers, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"-> {args.out}")
    else:
        json.dump(markers, sys.stdout, ensure_ascii=False, indent=2)
        print()


if __name__ == "__main__":
    main()
