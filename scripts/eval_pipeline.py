#!/usr/bin/env python3
"""eval_pipeline.py -- Evaluation 5.1/5.2 des Paper-Konzepts, ueber viele Panoramen.

Fuer jedes CC0-Referenzpanorama:
  1. synthetische Fisheye-Aufnahmen rendern (Pose bekannt, aber verschwiegen)
     -> Hugin stitcht daraus ein Panorama          [Zweig STITCHING]
  2. synthetische Pinhole-Aufnahmen rendern (Pose bekannt und genutzt)
     -> reproject_pano.py baut daraus ein Panorama [Zweig REPROJEKTION]
  3. beide gegen das Original messen (PSNR, SSIM, Abdeckung, Yaw-Versatz)

Damit vergleicht 5.2 die zwei Eingangsklassen des Papers auf DERSELBEN Szene und
gegen dieselbe Wahrheit, und 5.1 gibt die Stitching-Genauigkeit gegen eine
CC0-Referenz an.

Wichtig fuer die Einordnung: alle Aufnahmen teilen denselben Nodalpunkt, es gibt
also keine Parallaxe. Das ist der GUENSTIGSTE Fall fuers Stitching -- reale
Aufnahmen mit Nodalpunktversatz koennen nur schlechter werden. Die Zahlen sind
damit obere Schranken fuer den Stitching-Zweig.

  python scripts/eval_pipeline.py --out data/_eval/ergebnisse.csv
"""
import argparse
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCENES = REPO / "platform" / "dev-data" / "media" / "scenes"


def run(cmd):
    p = subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout).strip()[-500:])
    return p.stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(REPO / "data" / "_eval" / "ergebnisse.csv"))
    ap.add_argument("--work", default=str(REPO / "data" / "_eval"))
    ap.add_argument("--width", type=int, default=2048, help="Panoramabreite der Ausgabe")
    ap.add_argument("--n-fisheye", type=int, default=6)
    ap.add_argument("--fov-fisheye", type=float, default=180.0)
    ap.add_argument("--n-pinhole", type=int, default=6)
    ap.add_argument("--fov-pinhole", type=float, default=90.0)
    ap.add_argument("--limit", type=int, help="nur die ersten N Panoramen")
    args = ap.parse_args()

    panos = sorted(p / "pano.jpg" for p in SCENES.glob("ph-*") if (p / "pano.jpg").is_file())
    if args.limit:
        panos = panos[:args.limit]
    work = Path(args.work)
    work.mkdir(parents=True, exist_ok=True)
    print(f"{len(panos)} Referenzpanoramen\n")

    rows = []
    for i, pano in enumerate(panos, 1):
        sid = pano.parent.name
        print(f"[{i}/{len(panos)}] {sid}", flush=True)
        base = {"szene": sid}
        t0 = time.time()
        fd, pd = work / f"{sid}_fish", work / f"{sid}_pin"
        run([str(REPO / "scripts" / "pano_to_views.py"), str(pano), str(fd),
             "--model", "fisheye", "--n", str(args.n_fisheye),
             "--fov", str(args.fov_fisheye), "--size", "1600"])
        run([str(REPO / "scripts" / "pano_to_views.py"), str(pano), str(pd),
             "--model", "pinhole", "--n", str(args.n_pinhole),
             "--fov", str(args.fov_pinhole), "--size", "1400",
             "--zenith", "--nadir"])
        t_render = time.time() - t0

        # Die beiden Zweige laufen UNABHAENGIG. Zuerst brach ein Stitching-Fehler
        # die ganze Szene ab -- dadurch fehlte die Reprojektion an genau den drei
        # Szenen, an denen Stitching scheiterte, und ihre Robustheit war
        # systematisch untererfasst. Genau dort ist sie am interessantesten.
        for label in ("stitching", "reprojektion"):
            try:
                t1 = time.time()
                if label == "stitching":
                    img = work / f"{sid}_stitch.jpg"
                    run([str(REPO / "scripts" / "stitch_hugin.py"), str(fd), str(img),
                         "--fov", str(args.fov_fisheye), "--lens", "2",
                         "--width", str(args.width)])
                    cp = json.loads(Path(str(img) + ".json")
                                    .read_text(encoding="utf-8"))["kontrollpunkte"]
                    extra = []
                else:
                    img = work / f"{sid}_reproj.jpg"
                    run([str(REPO / "scripts" / "reproject_pano.py"),
                         str(pd / "poses.json"), str(pd), str(img),
                         "--w", str(args.width), "--sx", "-1", "--sy", "-1"])
                    cp, extra = "", ["--no-align"]
                dt = time.time() - t1
                js = work / f"{sid}_{label}.json"
                run([str(REPO / "scripts" / "eval_pano.py"), str(pano), str(img),
                     "--json", str(js), "--label", label] + extra)
                m = json.loads(js.read_text(encoding="utf-8"))
                rows.append({**base, "zweig": label, "status": "ok",
                             "psnr_db": m["psnr_db"], "ssim": m["ssim"],
                             "abdeckung_pct": m["abdeckung_pct"],
                             "yaw_versatz_deg": m["yaw_versatz_deg"],
                             "mae": m["mae_grauwert"], "sekunden": round(dt, 1),
                             "kontrollpunkte": cp, "render_s": round(t_render, 1)})
                print(f"    {label:14} PSNR {m['psnr_db']:6.2f} dB  "
                      f"SSIM {m['ssim']:.4f}  Abd {m['abdeckung_pct']:5.1f}%  "
                      f"Yaw {m['yaw_versatz_deg']:+6.2f}°", flush=True)
            except Exception as e:
                kurz = str(e).strip().splitlines()[-1][:90] if str(e).strip() else "?"
                print(f"    {label:14} FEHLGESCHLAGEN: {kurz}", flush=True)
                rows.append({**base, "zweig": label, "status": "fehler",
                             "psnr_db": "", "ssim": "", "abdeckung_pct": "",
                             "yaw_versatz_deg": "", "mae": "", "sekunden": "",
                             "kontrollpunkte": "", "render_s": round(t_render, 1),
                             "fehler": kurz})

    fields = ["szene", "zweig", "status", "psnr_db", "ssim", "abdeckung_pct",
              "yaw_versatz_deg", "mae", "sekunden", "kontrollpunkte", "render_s",
              "fehler"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\n-> {args.out}")

    import statistics as st
    print(f"\n{'Zweig':16} {'n':>3} {'PSNR dB':>18} {'SSIM':>16} {'Abdeckung':>11}")
    for zw in ("stitching", "reprojektion"):
        n_try = len([r for r in rows if r["zweig"] == zw])
        sel = [r for r in rows if r["zweig"] == zw and r["psnr_db"] != ""]
        print(f"  ({zw}: {len(sel)} von {n_try} Panoramen erfolgreich)")
        if not sel:
            continue
        p = [r["psnr_db"] for r in sel]
        s = [r["ssim"] for r in sel]
        a = [r["abdeckung_pct"] for r in sel]
        print(f"{zw:16} {len(sel):3}  {st.mean(p):6.2f} ± {st.stdev(p) if len(p)>1 else 0:4.2f}  "
              f"{st.mean(s):6.4f} ± {st.stdev(s) if len(s)>1 else 0:6.4f}  "
              f"{st.mean(a):8.1f}%")


if __name__ == "__main__":
    main()
