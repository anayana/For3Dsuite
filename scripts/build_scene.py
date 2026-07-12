#!/usr/bin/env python3
"""build_scene.py -- Mehrere E57-Setups zu einer begehbaren Szene verarbeiten.

Fuer jedes Setup: Panorama rendern + Punktwolke exportieren, ALLE mit demselben
Referenz-Ursprung rezentriert (erstes Setup = Referenz). So liegen die Punkt-
wolken aller Standpunkte in EINEM Weltkoordinatensystem (Scan-Schatten werden
gefuellt), und jeder Standpunkt bekommt seine reale Position -> StreetView-Tour.

Voraussetzung: die Einzel-Setup-E57 sind in einen gemeinsamen (registrierten)
Frame gebracht -- pruefbar daran, dass die Scanner-Origins (header.translation)
verschieden und raeumlich plausibel sind, nicht alle (0,0,0).

Ausgabe:
  viewer/data/scene_<id>_pano.jpg     (Panorama je Standpunkt)
  viewer/data/scene_<id>_points.bin   (Punktwolke je Standpunkt, gemeinsamer Frame)
  viewer/data/renon_scene.json        (Manifest: Standpunkte + Positionen)

Nutzung:
  python scripts/build_scene.py data/renon/e57/*.e57 [--w 4096] [--max 800000]
"""
import sys, os, json, glob, subprocess, argparse
import numpy as np
import pye57

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable

def scanner_origin(e57_path):
    """Scanner-Position im (gemeinsamen) E57-Frame = header.translation."""
    e = pye57.E57(e57_path)
    t = np.asarray(e.get_header(0).translation, float)
    return t

def setup_id(path):
    import re
    m = re.search(r'(\d{2,3})', os.path.basename(path))
    return m.group(1) if m else os.path.splitext(os.path.basename(path))[0]

def run(cmd):
    print("  $", " ".join(os.path.basename(c) if c.endswith('.py') else c for c in cmd))
    subprocess.run(cmd, check=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("e57", nargs="+", help="E57-Dateien (Glob erlaubt)")
    ap.add_argument("--w", type=int, default=4096, help="Panoramabreite je Standpunkt")
    ap.add_argument("--max", type=int, default=800000, help="max Punkte je Standpunkt")
    args = ap.parse_args()

    files = []
    for pat in args.e57:
        files += glob.glob(pat)
    files = sorted(set(files))
    if not files:
        sys.exit("Keine E57-Dateien gefunden.")

    outdir = os.path.join(ROOT, "viewer", "data")
    tmpdir = os.path.join(ROOT, "data", "renon", "_scene_tmp")
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(tmpdir, exist_ok=True)

    ref = scanner_origin(files[0])
    print(f"Referenz-Ursprung (Setup {setup_id(files[0])}): "
          f"({ref[0]:.3f}, {ref[1]:.3f}, {ref[2]:.3f})")

    nodes = []
    for f in files:
        sid = setup_id(f)
        print(f"\n=== Setup {sid} : {os.path.basename(f)} ===")
        S = scanner_origin(f)
        # Position im three.js-Weltframe (gleiche Rezentrierung wie e57_to_pointsbin):
        # (x-ox, z-oz, -(y-oy))
        pos = [float(S[0]-ref[0]), float(S[2]-ref[2]), float(-(S[1]-ref[1]))]
        dist = float(np.hypot(pos[0], np.hypot(pos[1], pos[2])))
        print(f"  Scanner-Origin (E57): ({S[0]:.2f},{S[1]:.2f},{S[2]:.2f})  "
              f"-> Weltpos ({pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f})  d={dist:.2f} m")

        # 1) Bilder + Posen
        imgdir = os.path.join(tmpdir, sid)
        run([PY, os.path.join(HERE, "e57_extract_images.py"), f, imgdir])
        stem = os.path.splitext(os.path.basename(f))[0]
        poses = os.path.join(imgdir, f"{stem}_poses.json")

        # 2) Panorama
        pano_rel = f"scene_{sid}_pano.jpg"
        run([PY, os.path.join(HERE, "reproject_pano.py"), poses, imgdir,
             os.path.join(outdir, pano_rel), "--w", str(args.w), "--sx", "1", "--sy", "-1"])

        # 3) Punktwolke im GEMEINSAMEN Frame (Referenz-Ursprung fuer alle gleich)
        pts_rel = f"scene_{sid}_points.bin"
        run([PY, os.path.join(HERE, "e57_to_pointsbin.py"), f,
             os.path.join(outdir, pts_rel), "--max", str(args.max),
             "--origin", f"{ref[0]},{ref[1]},{ref[2]}"])

        n = np.frombuffer(open(os.path.join(outdir, pts_rel), "rb").read(8)[4:8],
                          dtype="<u4")[0]
        nodes.append({"id": sid, "name": f"Setup {sid}", "pos": pos,
                      "pano": pano_rel, "points": pts_rel, "n": int(n)})

    manifest = {"ref_origin_e57": [float(v) for v in ref], "nodes": nodes}
    mf = os.path.join(outdir, "renon_scene.json")
    json.dump(manifest, open(mf, "w"), indent=2)
    print(f"\n-> {len(nodes)} Standpunkte, Manifest: {mf}")
    for nnode in nodes:
        print(f"   {nnode['id']}: pos {['%.1f'%v for v in nnode['pos']]}  "
              f"{nnode['n']:,} Punkte")

if __name__ == "__main__":
    main()
