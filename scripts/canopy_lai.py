#!/usr/bin/env python3
"""canopy_lai.py -- Kronenschluss/LAI auf ZWEI unabhaengigen Wegen fuer dieselbe Szene.

Rechnet fuer einen Standpunkt beide in der Forstpraxis ueblichen Schaetzungen und
stellt sie nebeneinander:

  optisch     Panorama -> aequidistantes Zenit-Fisheye (hemi_from_pano.py)
              -> hemispheR: Lueckenanteil je Zenitring -> Kronenoeffnung, LAI
  strukturell E57 -> LAS -> lidR: Boden klassifizieren, Hoehe normalisieren,
              MacArthur-Horn-Profil (LAD) -> ueber die Hoehe integriert

Das ist ausdruecklich KEINE Validierung des einen durch das andere: beide Wege
haben verschiedene, teils gegenlaeufige Verzerrungen (siehe LIMITS unten). Der
Wert liegt darin, dieselbe Groesse zweimal unabhaengig zu bestimmen und die
Differenz sichtbar zu machen, statt eine Zahl als Wahrheit auszugeben.

  python scripts/canopy_lai.py <scene-verzeichnis> --e57 <datei.e57> [--out canopy.json]

Beispiel:
  python scripts/canopy_lai.py platform/dev-data/media/scenes/renon-setup01 \
      --e57 "data/Renon/e57/Renon cp2- Setup 001.e57"
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RSCRIPT_CANDIDATES = [
    "Rscript",
    r"C:\Program Files\R\R-4.4.2\bin\Rscript.exe",
]


def find_rscript():
    for c in RSCRIPT_CANDIDATES:
        try:
            subprocess.run([c, "--version"], capture_output=True, check=True)
            return c
        except (OSError, subprocess.CalledProcessError):
            continue
    for base in Path(r"C:\Program Files\R").glob("R-*"):
        exe = base / "bin" / "Rscript.exe"
        if exe.is_file():
            return str(exe)
    raise SystemExit("Rscript nicht gefunden -- R installieren oder PATH setzen")


def e57_to_las(e57_path, las_path, max_points=3_000_000):
    """Scan 0 einer E57 als LAS ablegen (fuer lidR).

    Die Hoehennormalisierung macht bewusst lidR und nicht dieses Skript --
    classify_ground(csf) + normalize_height(tin) sind dort erprobt.
    """
    import laspy
    import pye57

    d = pye57.E57(str(e57_path)).read_scan(0, ignore_missing_fields=True,
                                           colors=False, intensity=True)
    xyz = np.c_[d["cartesianX"], d["cartesianY"], d["cartesianZ"]].astype(np.float64)
    if len(xyz) > max_points:
        sel = np.random.default_rng(0).choice(len(xyz), max_points, replace=False)
        xyz = xyz[sel]

    hdr = laspy.LasHeader(point_format=0, version="1.2")
    hdr.offsets = xyz.min(0)
    hdr.scales = np.array([0.001, 0.001, 0.001])
    las = laspy.LasData(hdr)
    las.x, las.y, las.z = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    las.write(str(las_path))
    print(f"  {len(xyz):,} Punkte -> {las_path.name}")
    return len(xyz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene_dir", help="Szenenordner mit pano.jpg")
    ap.add_argument("--e57", required=True, help="E57 desselben Standpunkts")
    ap.add_argument("--out", help="Ausgabe-JSON (Default: <scene_dir>/canopy.json)")
    ap.add_argument("--size", type=int, default=1400, help="Fisheye-Kantenlaenge")
    ap.add_argument("--max-vza", type=float, default=90.0)
    ap.add_argument("--keep-las", action="store_true", help="LAS nicht loeschen")
    args = ap.parse_args()

    scene = Path(args.scene_dir)
    pano = scene / "pano.jpg"
    if not pano.is_file():
        raise SystemExit(f"Kein Panorama: {pano}")
    out = Path(args.out) if args.out else scene / "canopy.json"

    print("1) Panorama -> hemisphaerisches Fisheye")
    # PNG fuer die Auswertung: JPEG-Artefakte wuerden die Otsu-Schwelle und
    # damit den Lueckenanteil verschieben. Die JPG-Kopie ist nur fuer den Viewer.
    hemi = scene / "hemi.png"
    subprocess.run([sys.executable, str(HERE / "hemi_from_pano.py"), str(pano),
                    str(hemi), "--size", str(args.size),
                    "--max-vza", str(args.max_vza)], check=True)
    from PIL import Image
    Image.open(hemi).convert("RGB").save(scene / "hemi.jpg", quality=88)

    print("2) E57 -> LAS")
    las = scene / "_canopy_tmp.las"
    n_pts = e57_to_las(args.e57, las)

    print("3) hemispheR + lidR")
    rscript = find_rscript()
    r = subprocess.run([rscript, str(HERE / "canopy_lai.R"), str(hemi), str(las),
                        str(out), str(args.max_vza)],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    if r.returncode != 0:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"R-Auswertung fehlgeschlagen (Code {r.returncode})")

    if not args.keep_las:
        las.unlink(missing_ok=True)

    res = json.loads(out.read_text(encoding="utf-8"))
    res["punkte_las"] = n_pts
    res["fisheye"] = f"scenes/{scene.name}/hemi.jpg"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    # Ins Szenen-Manifest haengen, damit der Viewer es anzeigen kann
    sj = scene / "scene.json"
    if sj.is_file():
        s = json.loads(sj.read_text(encoding="utf-8"))
        s["canopy"] = res
        sj.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   scene.json ergaenzt (canopy)")

    o, s = res["optisch"], res["strukturell"]
    fmt = lambda v: "n/a" if v is None else f"{float(v):.2f}"
    print(f"\n  optisch     (hemispheR): LAI {fmt(o['lai'])}   "
          f"Himmelsanteil {fmt(o['openness_pct'])} %")
    print(f"  strukturell (lidR)     : LAI {fmt(s['lai'])}   "
          f"Bestandeshoehe {fmt(s['hoehe_p95_m'])} m")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
