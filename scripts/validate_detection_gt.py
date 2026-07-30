#!/usr/bin/env python3
"""validate_detection_gt.py -- Stammdetektion gegen semantische Ground Truth pruefen.

Bisher liess sich in dieser Suite nur die UEBEREINSTIMMUNG von Verfahren messen
(dbh_methods.py am Renon-Bestand: kein Feldmass, also keine Genauigkeit) oder die
Genauigkeit an fuenf Einzelbaeumen (BENCH_DBH.md, SYSSIFOSS). SegmentedForests
schliesst die Luecke: dort ist JEDER PUNKT eines ganzen Plots manuell klassiert.

Damit sind zwei Fragen zum ersten Mal beantwortbar, die bisher offen blieben:

  1. RECALL   Wie viele der wirklich vorhandenen Staemme findet die Detektion?
              Referenz sind die als Stamm gelabelten Punkte, geclustert.
  2. PRECISION / FEHLALARME
              Worauf sitzen die Detektionen, die KEIN Stamm sind? Der Datensatz
              labelt genau die Klassen, die als Fehldetektion in Frage kommen --
              liegendes Totholz, Stubben, Steine, Straeucher, Personen. Statt
              "vermutlich Totholz" steht dann da, was es wirklich war.

Das prueft zugleich den Schaftkontroll-Filter aus dbh_methods.py, der am
Renon-Bestand 18 Detektionen verworfen hat, ohne dass sich das belegen liess.

  python scripts/validate_detection_gt.py <analysis.npz> <stems.csv> \\
      --classes data/segforests/classes.json --out bericht.json
"""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

CELL_GROUND = 0.5
SLICE_LO, SLICE_HI = 1.05, 1.55


def ground_grid(xyz, cell=CELL_GROUND):
    ix = np.floor(xyz[:, 0] / cell).astype(np.int64)
    iy = np.floor(xyz[:, 1] / cell).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], xyz[order, 2]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    g = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 20:
            g[int(ks[lo])] = float(np.percentile(zs[lo:hi], 2))
    return g, key


def cluster_xy(pts, cell=0.10, min_pts=30):
    """Zusammenhangskomponenten im XY-Raster -> Liste von Punktindizes."""
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iy = np.floor(pts[:, 1] / cell).astype(np.int64)
    cells = {}
    for i, (a, b) in enumerate(zip(ix, iy)):
        cells.setdefault((int(a), int(b)), []).append(i)
    seen, out = set(), []
    for start in cells:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            c = stack.pop()
            comp.append(c)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (c[0] + dx, c[1] + dy)
                    if nb in cells and nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        idx = np.array([i for c in comp for i in cells[c]])
        if len(idx) >= min_pts:
            out.append(idx)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cloud", help="Analyse-.npz mit 'cls' (laz_analysis.py)")
    ap.add_argument("stems", help="Detektionen (CSV mit x,y[,label,BHD_cm])")
    ap.add_argument("--classes", required=True,
                    help="JSON: {\"stem\": [codes], \"names\": {code: name}}")
    ap.add_argument("--out", help="Bericht als JSON")
    ap.add_argument("--match-dist", type=float, default=0.6,
                    help="max. Abstand Detektion <-> Referenzstamm [m]")
    ap.add_argument("--stem-radius", type=float, default=0.4,
                    help="Umkreis um die Detektion, dessen Labels zaehlen [m]")
    args = ap.parse_args()

    d = np.load(args.cloud, allow_pickle=False)
    if "cls" not in d:
        raise SystemExit("Die Wolke hat keine 'cls'-Spalte -- laz_analysis.py nutzen")
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    cls = d["cls"]
    spec = json.loads(Path(args.classes).read_text(encoding="utf-8"))
    stem_codes = set(spec["stem"])
    names = {int(k): v for k, v in spec.get("names", {}).items()}
    print(f"{len(xyz):,} Punkte, {len(np.unique(cls))} Klassen; "
          f"Stammklassen {sorted(stem_codes)}")

    ground, gkey = ground_grid(xyz)
    default_g = float(np.median(list(ground.values()))) if ground else float(xyz[:, 2].min())
    gz = np.array([ground.get(int(k), default_g) for k in gkey])
    h = xyz[:, 2] - gz
    in_slice = (h >= SLICE_LO) & (h <= SLICE_HI)

    is_stem = np.isin(cls, list(stem_codes))

    # ---- Referenzstaemme: gelabelte Stammpunkte der Brusthoehen-Scheibe clustern
    ref_idx = np.flatnonzero(in_slice & is_stem)
    print(f"{len(ref_idx):,} gelabelte Stammpunkte in der Brusthoehen-Scheibe")
    refs = []
    for c in cluster_xy(xyz[ref_idx]):
        p = xyz[ref_idx[c]]
        cx, cy = float(p[:, 0].mean()), float(p[:, 1].mean())
        # Referenz-Durchmesser: doppelter Medianabstand zum Schwerpunkt. Bei
        # einseitig gescanntem Stamm ist das zu klein -- daher nur als Hinweis,
        # nicht als Ground-Truth-BHD ausgewiesen.
        rad = float(np.median(np.hypot(p[:, 0] - cx, p[:, 1] - cy)))
        refs.append({"x": round(cx, 3), "y": round(cy, 3),
                     "punkte": int(len(c)), "radius_med_cm": round(100 * rad, 1)})
    print(f"{len(refs)} Referenzstaemme aus den Labels")

    # ---- Detektionen einlesen und je Detektion die Labels im Umkreis auszaehlen
    det = list(csv.DictReader(open(args.stems, encoding="utf-8-sig")))
    print(f"{len(det)} Detektionen aus {Path(args.stems).name}")
    sl_xyz = xyz[in_slice]
    sl_cls = cls[in_slice]
    used = set()
    rows = []
    for i, t in enumerate(det):
        dx, dy = float(t["x"]), float(t["y"])
        near = np.hypot(sl_xyz[:, 0] - dx, sl_xyz[:, 1] - dy) <= args.stem_radius
        counts = Counter(int(c) for c in sl_cls[near])
        total = sum(counts.values())
        stem_share = (sum(v for k, v in counts.items() if k in stem_codes) / total
                      if total else 0.0)
        top = counts.most_common(1)[0][0] if counts else None
        # naechster noch freier Referenzstamm
        best, bestd = None, None
        for j, r in enumerate(refs):
            if j in used:
                continue
            dd = math.hypot(r["x"] - dx, r["y"] - dy)
            if bestd is None or dd < bestd:
                best, bestd = j, dd
        matched = best is not None and bestd <= args.match_dist
        if matched:
            used.add(best)
        rows.append({
            "id": t.get("label") or t.get("id") or f"d{i+1}",
            "x": round(dx, 3), "y": round(dy, 3),
            "treffer": "ja" if matched else "nein",
            "abstand_m": round(bestd, 2) if bestd is not None else None,
            "punkte_im_umkreis": total,
            "stammanteil_pct": round(100 * stem_share, 1),
            "haeufigste_klasse": names.get(top, str(top)) if top is not None else None,
        })

    n_hit = sum(1 for r in rows if r["treffer"] == "ja")
    recall = n_hit / len(refs) if refs else 0.0
    precision = n_hit / len(rows) if rows else 0.0
    print(f"\nRecall    {100*recall:5.1f}%  ({n_hit}/{len(refs)} Referenzstaemme gefunden)")
    print(f"Precision {100*precision:5.1f}%  ({n_hit}/{len(rows)} Detektionen sind Staemme)")

    # Worauf sitzen die Fehlalarme? Genau das war am Renon-Bestand nicht belegbar.
    fp = [r for r in rows if r["treffer"] == "nein"]
    fp_classes = Counter(r["haeufigste_klasse"] for r in fp)
    if fp:
        print(f"\n{len(fp)} Fehlalarme sitzen auf:")
        for k, v in fp_classes.most_common():
            print(f"   {v:3}x {k}")

    report = {
        "wolke": Path(args.cloud).name,
        "detektionen": len(rows), "referenzstaemme": len(refs),
        "treffer": n_hit,
        "recall": round(recall, 3), "precision": round(precision, 3),
        "match_dist_m": args.match_dist,
        "fehlalarm_klassen": dict(fp_classes),
        "je_detektion": rows,
        "hinweis": ("Referenzstaemme = geclusterte, MANUELL als Stamm gelabelte "
                    "Punkte der Brusthoehen-Scheibe. Der Datensatz ist semantisch "
                    "(Klasse je Punkt), nicht instanzweise gelabelt -- die Trennung "
                    "in einzelne Staemme stammt also aus dem Clustering hier und "
                    "kann bei sich beruehrenden Staemmen verschmelzen."),
    }
    if args.out:
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"\n-> {args.out}")


if __name__ == "__main__":
    main()
