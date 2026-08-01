#!/usr/bin/env python3
"""eval_seams.py -- Nahtversatz OHNE Referenzpanorama, aus den Ueberlappungen.

Die Evaluation in eval_pano.py braucht ein wahres Panorama und funktioniert
deshalb nur mit synthetischen Aufnahmen. Reale Aufnahmen haben keine Wahrheit --
aber sie haben etwas anderes: in den UEBERLAPPUNGEN zeigen zwei Quellbilder
dieselbe Blickrichtung. Waeren Registrierung und Nodalpunkt perfekt, muessten sie
dort identisch sein. Ihre lokale Verschiebung IST der Fehler -- Parallaxe plus
Registrierungsrest, gemessen ohne jede Referenz.

Damit laesst sich der Vorbehalt aufloesen, dass die synthetischen Zahlen (alle
Aufnahmen teilen einen Nodalpunkt) nur obere Schranken sind: dasselbe Mass, auf
synthetische und auf reale Saetze angewandt, zeigt, was die reale Parallaxe kostet.

Verfahren: nona remappt jede Aufnahme einzeln in die Panoramaflaeche (TIFF_m).
Fuer jedes Bildpaar mit gemeinsamer Abdeckung wird die Ueberlappung blockweise
per Phasenkorrelation verglichen. Berichtet werden Median, p95 und der Anteil
ueber 1 px -- in Pixeln und in Grad der Panoramaflaeche.

  python scripts/eval_seams.py <bilderverzeichnis> --fov 180 --lens 2 --width 4096
  python scripts/eval_seams.py <bilderverzeichnis> --pto vorhandenes_projekt.pto
"""
import argparse
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HUGIN_DEFAULT = r"C:\Program Files\Hugin\bin"
IMG_EXT = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}


def tool(bindir, name):
    exe = Path(bindir) / (name + (".exe" if os.name == "nt" else ""))
    if not exe.is_file():
        raise SystemExit(f"Hugin-Werkzeug fehlt: {exe}")
    return str(exe)


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if p.returncode != 0:
        tail = (p.stderr or p.stdout or "").strip().splitlines()[-5:]
        raise SystemExit(f"{Path(cmd[0]).stem} fehlgeschlagen:\n  " + "\n  ".join(tail))
    return p


def uncrop(pto):
    """r:CROP aus der Ausgabezeile nehmen -- wir brauchen volle Leinwaende.

    nona schreibt sonst beschnittene Kacheln mit Versatz in den TIFF-Tags; fuer
    den paarweisen Vergleich muessen alle Kacheln dasselbe Koordinatensystem
    haben.
    """
    t = Path(pto).read_text(errors="replace")
    t = re.sub(r'(n"TIFF_m[^"]*?)\s*r:CROP', r"\1", t)
    Path(pto).write_text(t)


def load_tile(path):
    """Remappte Kachel -> (Grauwert float32, Maske bool)."""
    im = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if im is None:
        return None, None
    if im.dtype == np.uint16:
        im = (im / 257).astype(np.uint8)
    if im.ndim == 3 and im.shape[2] == 4:
        mask = im[:, :, 3] > 0
        g = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)
    elif im.ndim == 3:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        mask = g > 0
    else:
        g, mask = im, im > 0
    return g.astype(np.float32), mask


def pair_offsets(a, ma, b, mb, block=64, step=48, max_px=30.0, min_resp=0.05):
    """Lokale Verschiebungen in der gemeinsamen Abdeckung zweier Kacheln."""
    both = ma & mb
    if both.sum() < block * block * 4:
        return []
    ys, xs = np.where(both)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    win = cv2.createHanningWindow((block, block), cv2.CV_32F)
    out = []
    for y in range(y0, max(y1 - block, y0) + 1, step):
        for x in range(x0, max(x1 - block, x0) + 1, step):
            m = both[y:y + block, x:x + block]
            if m.shape != (block, block) or m.mean() < 0.99:
                continue
            pa = a[y:y + block, x:x + block]
            pb = b[y:y + block, x:x + block]
            if pa.std() < 8 or pb.std() < 8:
                continue                       # strukturlos -> keine Aussage
            (dx, dy), resp = cv2.phaseCorrelate(np.ascontiguousarray(pa),
                                                np.ascontiguousarray(pb), win)
            d = float(np.hypot(dx, dy))
            if resp >= min_resp and d <= max_px:
                out.append(d)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("imgdir")
    ap.add_argument("--pto", help="fertiges Hugin-Projekt statt eigener Registrierung")
    ap.add_argument("--fov", type=float, default=180.0)
    ap.add_argument("--lens", type=int, default=2)
    ap.add_argument("--width", type=int, default=4096)
    ap.add_argument("--hugin-bin", default=os.environ.get("HUGIN_BIN", HUGIN_DEFAULT))
    ap.add_argument("--json", help="Ergebnis als JSON")
    ap.add_argument("--label", default="")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    src = Path(args.imgdir).resolve()
    imgs = sorted(p.name for p in src.iterdir() if p.suffix.lower() in IMG_EXT)
    if len(imgs) < 2:
        raise SystemExit(f"Mindestens zwei Bilder noetig, gefunden {len(imgs)}")
    work = src / "_seams"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()

    T = lambda n: tool(args.hugin_bin, n)          # noqa: E731
    if args.pto:
        shutil.copy2(args.pto, work / "p.pto")
        for n in imgs:
            shutil.copy2(src / n, work / n)
        print(f"Projekt uebernommen: {Path(args.pto).name}")
    else:
        for n in imgs:
            shutil.copy2(src / n, work / n)
        print(f"Registriere {len(imgs)} Aufnahmen (FOV {args.fov:g}, Objektiv {args.lens})")
        run([T("pto_gen"), "-o", "p.pto", "-p", str(args.lens), "-f", str(args.fov)]
            + imgs, work)
        run([T("cpfind"), "--multirow", "-o", "p.pto", "p.pto"], work)
        run([T("cpclean"), "-o", "p.pto", "p.pto"], work)
        run([T("autooptimiser"), "-a", "-m", "-l", "-s", "-o", "p.pto", "p.pto"], work)
    run([T("pano_modify"), "-p", "2", "--fov=360x180",
         f"--canvas={args.width}x{args.width // 2}", "-o", "p.pto", "p.pto"], work)
    uncrop(work / "p.pto")
    run([T("nona"), "-m", "TIFF_m", "-o", "rem", "p.pto"], work)

    tiles = sorted(work.glob("rem*.tif"))
    print(f"{len(tiles)} remappte Kacheln")
    data = {}
    for t in tiles:
        g, m = load_tile(t)
        if g is not None and m.any():
            data[t.name] = (g, m)

    all_d, pairs = [], 0
    for a, b in itertools.combinations(sorted(data), 2):
        d = pair_offsets(*data[a], *data[b])
        if len(d) >= 5:
            pairs += 1
            all_d += d
    if not all_d:
        raise SystemExit("Keine auswertbaren Ueberlappungen gefunden")

    arr = np.array(all_d)
    deg = 360.0 / args.width
    res = {"label": args.label or src.name, "aufnahmen": len(imgs),
           "bildpaare_mit_ueberlappung": pairs, "messbloecke": len(arr),
           "median_px": round(float(np.median(arr)), 2),
           "p95_px": round(float(np.percentile(arr, 95)), 2),
           "max_px": round(float(arr.max()), 2),
           "median_deg": round(float(np.median(arr)) * deg, 4),
           "anteil_ueber_1px_pct": round(100.0 * float((arr > 1).mean()), 1),
           "panoramabreite": args.width,
           "quelle": "eigene Registrierung" if not args.pto else Path(args.pto).name}
    print(f"\n{res['label']}: {pairs} ueberlappende Paare, {len(arr)} Bloecke")
    print(f"  Nahtversatz  Median {res['median_px']:.2f} px  p95 {res['p95_px']:.2f} px  "
          f"max {res['max_px']:.2f} px")
    print(f"  ueber 1 px:  {res['anteil_ueber_1px_pct']:.1f} % der Bloecke")
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        print(f"-> {args.json}")
    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
