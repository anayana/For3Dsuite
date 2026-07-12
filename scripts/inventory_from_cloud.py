#!/usr/bin/env python3
"""inventory_from_cloud.py -- Einzelbaum-Inventur aus einer TLS-Punktwolke (Baseline).

Einfache, abhaengigkeitsarme Stammerkennung (nur numpy) als Referenz-Baseline;
fuer publikationsreife Genauigkeit spaeter mit lidR/TreeLS oder 3DFin vergleichen.

Verfahren:
  1. Bodenmodell: 0,5-m-Raster, je Zelle 2. Perzentil der z-Werte
  2. Brusthoehen-Scheibe: Punkte mit BH_LO <= (z - Boden) <= BH_HI
  3. Clusterung der Scheibe im XY-Belegungsraster (Zusammenhangskomponenten)
  4. Kreis-Fit (Kasa) je Cluster -> Position + BHD; Plausibilitaetsfilter
  5. Ableitungen: Grundflaeche = pi*(BHD/2)^2; Baumhoehe = max(z)-Boden im
     1,5-m-Umkreis (nur bei ausreichend hoher Wolke; sonst als "erfasst" markiert);
     Schaftvolumen = Grundflaeche*Hoehe*Formfaktor (nur bei valider Hoehe).

Die Detektions-Schwellen sind per CLI einstellbar: dichte stationaere TLS (Renon)
vertraegt strenge Defaults; duenne mobile Scans (TreeScope) brauchen kleinere
--min-points und --arc-min. Baseline (numpy); fuer publikationsreife Genauigkeit
gegen lidR/TreeLS oder 3DFin vergleichen und an Referenzinventur validieren.

Nutzung:
  python inventory_from_cloud.py <datei.e57|.las|.pcd> <out.csv>
      [--origin X Y Z] [--radius 18] [--min-points 40] [--arc-min 90]
      [--rms-max 3] [--bh 1.0 1.6] [--min-tree-height 5] [--form-factor 0.5]
"""
import argparse
import csv
import math
import sys
from collections import deque

import numpy as np

CELL_GROUND = 0.5   # m, Bodenraster
CELL_STEM = 0.04    # m, Belegungsraster der Brusthoehen-Scheibe
R_MIN, R_MAX = 0.04, 0.75  # m, plausibler Stammradius (BHD 8..150 cm)


def load_points(path):
    low = path.lower()
    if low.endswith(".e57"):
        import pye57
        d = pye57.E57(path).read_scan(0, ignore_missing_fields=True)
        return d["cartesianX"], d["cartesianY"], d["cartesianZ"]
    if low.endswith(".pcd"):
        from pcd_io import read_pcd
        x, y, z, _ = read_pcd(path)
        return x, y, z
    import laspy
    las = laspy.read(path)
    return np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)


def ground_model(x, y, z):
    """Dict Zelle -> Bodenhoehe (2. Perzentil der z in der Zelle)."""
    ix = np.floor(x / CELL_GROUND).astype(np.int64)
    iy = np.floor(y / CELL_GROUND).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    key_s, z_s = key[order], z[order]
    bounds = np.flatnonzero(np.diff(key_s)) + 1
    ground = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(key_s)]):
        if hi - lo >= 20:
            ground[key_s[lo]] = float(np.percentile(z_s[lo:hi], 2))
    return ground, key


def fit_circle(px, py):
    """Kasa-Fit: Zentrum, Radius, RMS-Residuum, Winkelabdeckung in Grad."""
    A = np.c_[px, py, np.ones_like(px)]
    b = px**2 + py**2
    try:
        (a, c, d), *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = a / 2, c / 2
    r2 = d + cx**2 + cy**2
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    dist = np.hypot(px - cx, py - cy)
    rms = float(np.sqrt(np.mean((dist - r) ** 2)))
    ang = np.degrees(np.arctan2(py - cy, px - cx))
    hist = np.histogram(ang, bins=36, range=(-180, 180))[0]
    arc = float(np.count_nonzero(hist)) * 10.0
    return cx, cy, r, rms, arc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cloud", help=".e57 oder .las")
    ap.add_argument("out", help="Ausgabe-CSV (x,y,z,label,BHD_cm,Hoehe_m,...)")
    ap.add_argument("--origin", nargs=3, type=float, metavar=("X", "Y", "Z"),
                    help="Scan-Ursprung; begrenzt die Auswertung auf --radius")
    ap.add_argument("--radius", type=float, default=18.0)
    ap.add_argument("--min-points", type=int, default=40,
                    help="Mindestpunktzahl je Stamm-Cluster (mobil/duenn: ~20)")
    ap.add_argument("--arc-min", type=float, default=90.0,
                    help="Mindest-Winkelabdeckung des Kreis-Fits in Grad")
    ap.add_argument("--rms-max", type=float, default=3.0,
                    help="max. Kreis-Fit-Residuum in cm")
    ap.add_argument("--bh", nargs=2, type=float, default=[1.0, 1.6],
                    metavar=("LO", "HI"), help="Brusthoehen-Band ueber Boden [m]")
    ap.add_argument("--min-tree-height", type=float, default=5.0,
                    help="ab dieser erfassten Hoehe gilt max(z) als Baumhoehe; "
                         "darunter ist die Wolke gekappt -> Hoehe nur 'erfasst'")
    ap.add_argument("--form-factor", type=float, default=0.5,
                    help="Schaftformfaktor fuer das Volumen (Fichte ~0,5)")
    ap.add_argument("--nms-dist", type=float, default=0.6,
                    help="Mindestabstand zwischen Staemmen [m] (Duplikat-Unterdrueckung)")
    args = ap.parse_args()
    bh_lo, bh_hi = args.bh

    x, y, z = load_points(args.cloud)
    print(f"{len(x):,} Punkte geladen")
    if args.origin:
        ox, oy, _ = args.origin
        m = np.hypot(x - ox, y - oy) <= args.radius
        x, y, z = x[m], y[m], z[m]
        print(f"{len(x):,} Punkte im {args.radius:.0f}-m-Umkreis des Ursprungs")

    ground, gkey = ground_model(x, y, z)
    gz = np.array([ground.get(k, np.nan) for k in gkey])
    hbh = z - gz
    sl = (hbh >= bh_lo) & (hbh <= bh_hi)
    sx, sy, sz, sh = x[sl], y[sl], z[sl], hbh[sl]
    print(f"{int(sl.sum()):,} Punkte im Detektionsband ({bh_lo}-{bh_hi} m ueber Boden)")
    # Schmales Messfenster um 1,3 m fuer den eigentlichen BHD-Fit (Stammverjuengung
    # ueber ein breites Band wuerde den Durchmesser verfaelschen)
    MEAS_LO, MEAS_HI = 1.05, 1.55

    # Belegungsraster + Zusammenhangskomponenten (8er-Nachbarschaft)
    cix = np.floor(sx / CELL_STEM).astype(np.int64)
    ciy = np.floor(sy / CELL_STEM).astype(np.int64)
    cells = {}
    for i, (a, b) in enumerate(zip(cix, ciy)):
        cells.setdefault((int(a), int(b)), []).append(i)

    seen, clusters = set(), []
    for start in cells:
        if start in seen:
            continue
        comp, q = [], deque([start])
        seen.add(start)
        while q:
            cell = q.popleft()
            comp.append(cell)
            cx0, cy0 = cell
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (cx0 + dx, cy0 + dy)
                    if nb in cells and nb not in seen:
                        seen.add(nb)
                        q.append(nb)
        idx = [i for cell in comp for i in cells[cell]]
        if len(idx) >= args.min_points:
            clusters.append(np.array(idx))
    print(f"{len(clusters)} Kandidaten-Cluster")

    rms_max_m = args.rms_max / 100.0
    trees, rejected = [], 0
    for idx in clusters:
        # BHD bevorzugt aus dem schmalen Messfenster um 1,3 m (verjuengungsarm);
        # bei zu duenner Erfassung ersatzweise der ganze Cluster
        sub = idx[(sh[idx] >= MEAS_LO) & (sh[idx] <= MEAS_HI)]
        fit_idx = sub if len(sub) >= 6 else idx
        fit = fit_circle(sx[fit_idx], sy[fit_idx])
        if fit is None:
            rejected += 1
            continue
        cx, cy, r, rms, arc = fit
        if not (R_MIN <= r <= R_MAX) or rms > rms_max_m or arc < args.arc_min:
            rejected += 1
            continue
        gk = int(np.floor(cx / CELL_GROUND)) * 1_000_003 + int(np.floor(cy / CELL_GROUND))
        g = ground.get(gk)
        if g is None:
            g = float(np.nanmedian(gz[idx])) if np.isfinite(gz[idx]).any() else None
        if g is None:
            rejected += 1
            continue
        near = np.hypot(x - cx, y - cy) <= 1.5
        top = float(z[near].max() - g) if near.any() else float("nan")
        bhd_cm = 2 * r * 100
        basal_m2 = math.pi * r * r            # Grundflaeche in m^2
        # Hoehe nur als Baumhoehe werten, wenn die Wolke hoch genug reicht,
        # sonst ist die Krone gekappt (mobile Low-Scans) -> als "erfasst" markieren
        tree = {
            "x": round(cx, 3), "y": round(cy, 3), "z": round(g + 1.3, 3),
            "BHD_cm": round(bhd_cm, 1),
            "Grundflaeche_m2": round(basal_m2, 4),
            "Fit_RMS_cm": round(rms * 100, 1),
            "Bogen_deg": int(arc),
            "Punkte": int(len(idx)),
        }
        if math.isfinite(top) and top >= args.min_tree_height:
            tree["Hoehe_m"] = round(top, 1)
            tree["Volumen_m3"] = round(basal_m2 * top * args.form_factor, 3)
        else:
            tree["Hoehe_m"] = ""
            tree["erfasste_Hoehe_m"] = round(top, 1) if math.isfinite(top) else ""
        trees.append(tree)
    # Duplikate unterdruecken: bester Fit (viele Punkte, kleines Residuum) gewinnt,
    # weitere Detektionen im NMS_DIST-Umkreis (Aeste, Doppel-Fits) fliegen raus.
    trees.sort(key=lambda t: (-t["Punkte"], t["Fit_RMS_cm"]))
    kept = []
    for t in trees:
        if all(math.hypot(t["x"] - k["x"], t["y"] - k["y"]) >= args.nms_dist for k in kept):
            kept.append(t)
    dups = len(trees) - len(kept)
    trees = sorted(kept, key=lambda t: -t["BHD_cm"])
    for i, t in enumerate(trees, 1):
        t["label"] = f"Baum {i:02d}"

    if not trees:
        sys.exit(f"Keine Staemme gefunden ({rejected} Kandidaten verworfen)")
    fields = ["x", "y", "z", "label", "BHD_cm", "Grundflaeche_m2", "Hoehe_m",
              "Volumen_m3", "erfasste_Hoehe_m", "Fit_RMS_cm", "Bogen_deg", "Punkte"]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for t in trees:
            w.writerow({k: t.get(k, "") for k in fields})
    n_h = sum(1 for t in trees if t.get("Hoehe_m") != "")
    print(f"-> {args.out}: {len(trees)} Staemme "
          f"({rejected} Kandidaten verworfen, {dups} Duplikate unterdrueckt; "
          f"{n_h} mit valider Baumhoehe)")
    ba = sum(t["Grundflaeche_m2"] for t in trees)
    print(f"   Summe Grundflaeche der Detektionen: {ba:.2f} m^2")
    for t in trees[:12]:
        h = f"{t['Hoehe_m']} m" if t.get("Hoehe_m") != "" else f"(erfasst {t.get('erfasste_Hoehe_m','?')} m)"
        print(f"   {t['label']}: BHD {t['BHD_cm']:5.1f} cm  Grundfl {t['Grundflaeche_m2']:.3f} m2  "
              f"Hoehe {h}  ({t['x']:.2f}, {t['y']:.2f})  RMS {t['Fit_RMS_cm']} cm")


if __name__ == "__main__":
    main()
