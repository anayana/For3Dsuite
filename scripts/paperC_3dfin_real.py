#!/usr/bin/env python3
"""paperC_3dfin_real.py -- 3DFin auf ECHTEN Plotwolken mit kuenstlich reduzierter Abdeckung (Paper C).

Eingabe: komplette Plotwolke (SegmentedForests .laz, Mehrfachscan) und die 3DFin-INI
der Datensatzautoren. Vorgehen:
  1. Wolke auf 2-cm-Voxel ausduennen; 3DFin mit der Autoren-INI auf der VOLLEN Wolke
     -> Referenzstaemme (Position, BHD) = Abdeckung, die der Datensatz hergibt;
     alle Detektionen dienen als Verdecker.
  2. Virtuelle Scanner-Standpunkte (n = 1, 2, 3, 4, 6 im Raster per Greedy-Maximin;
     4 eng um die Plotmitte). Fuer jeden Standpunkt bleibt nur, was er sehen kann:
     Stammverdeckungsmodell in der Ebene -- ein Punkt faellt weg, wenn die
     Sichtlinie einen anderen Referenzstamm (Kreis mit BHD) kreuzt oder wenn er auf
     der abgewandten Seite seines eigenen Stammes liegt. Aeste und Laub verdecken in
     diesem Modell nicht (Abdeckung eher ueberschaetzt -> zugunsten von 3DFin).
  3. 3DFin mit derselben INI auf der Vereinigung der Standpunkte.
  4. Je Referenzstamm: geometrisch sichtbarer Bogen in 1,3 m (360 Umfangspunkte,
     Ausrichtung + Verdeckung, wie paperC_eval.visibility), Detektion (naechste
     3DFin-Position <= 0,5 m), BHD (0 = gefunden, aber BHD verworfen).

  python scripts/paperC_3dfin_real.py raw/plot_06.laz extdata/segforests/plot_06.ini --out out/fin_06.csv
"""
import argparse
import csv
import sys
from pathlib import Path

import numpy as np

NS = [1, 2, 3, 4, 6]


def run_fin(xyz, ini, work):
    import laspy
    from three_d_fin.processing.configuration import FinConfiguration
    from three_d_fin.processing.standalone_processing import StandaloneLASProcessing
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(errors="replace")
    work.mkdir(parents=True, exist_ok=True)
    off = xyz.min(axis=0)
    hdr = laspy.LasHeader(point_format=3); hdr.offsets = [0.0] * 3; hdr.scales = [0.001] * 3
    las = laspy.LasData(hdr); loc = xyz - off
    las.x, las.y, las.z = loc[:, 0], loc[:, 1], loc[:, 2]
    las.write(str(work / "plot.las"))
    # [misc] der Autoren-INI zeigt auf deren Rechner (F:\\...) -> ohne misc laden, misc selbst setzen
    import configparser
    cp = configparser.ConfigParser(); cp.read(ini)
    cp.remove_section("misc")
    with open(work / "fin.ini", "w") as fh:
        cp.write(fh)
    cfg = FinConfiguration.From_config_file(work / "fin.ini", init_misc=True)
    copy = lambda o, **u: (getattr(o, "model_copy", None) or o.copy)(update=u)   # pydantic 1/2
    misc = copy(cfg.misc, input_file=work / "plot.las", output_dir=work,
                is_normalized=False, is_noisy=True, export_txt=True)
    try:
        StandaloneLASProcessing(copy(cfg, misc=misc)).process()
    except Exception as e:
        print(f"  3DFin abgebrochen: {type(e).__name__}: {e}", flush=True)
        return np.zeros((0, 3))
    f = work / "plot_dbh_and_heights.txt"
    if not f.exists():
        return np.zeros((0, 3))
    out = []
    for r in f.read_text().splitlines():
        p = r.split()
        try:
            out.append((float(p[2]) + off[0], float(p[3]) + off[1], float(p[1]) * 100))
        except (IndexError, ValueError):
            continue
    return np.array(out).reshape(-1, 3)


def visible_points(xy, sp, stems):
    """Bool je Punkt: von Standpunkt sp aus sichtbar (Stammverdeckung in der Ebene)."""
    v = xy - sp; d = np.hypot(v[:, 0], v[:, 1]); th = np.arctan2(v[:, 1], v[:, 0])
    vis = np.ones(len(xy), bool)
    for cx, cy, r in stems:
        dc = np.hypot(cx - sp[0], cy - sp[1])
        if dc <= r:
            continue
        al = np.arcsin(min(r / dc, 1.0)); tc = np.arctan2(cy - sp[1], cx - sp[0])
        dth = np.abs((th - tc + np.pi) % (2 * np.pi) - np.pi)
        own = np.hypot(xy[:, 0] - cx, xy[:, 1] - cy) <= r + .05
        # Abstand zur Vorderseite des Kreises entlang der Sichtlinie
        near = dc * np.cos(dth) - np.sqrt(np.maximum(r * r - (dc * np.sin(dth)) ** 2, 0))
        hide = (dth < al) & (d > near + .02)
        # eigene Stammpunkte: nur die zugewandte Seite
        face = ((xy[:, 0] - cx) * (sp[0] - xy[:, 0]) + (xy[:, 1] - cy) * (sp[1] - xy[:, 1])) > 0
        vis &= np.where(own, face, ~hide)
    return vis


def arc_visible(stems, idx, sps, nang=360):
    cx, cy, r = stems[idx]
    th = np.linspace(0, 2 * np.pi, nang, endpoint=False)
    P = np.stack([cx + r * np.cos(th), cy + r * np.sin(th)], 1)
    others = np.delete(stems, idx, axis=0)
    seen = np.zeros(nang, bool)
    for sp in sps:
        u = sp - P; d = np.hypot(u[:, 0], u[:, 1]); u = u / d[:, None]
        ok = (np.cos(th) * u[:, 0] + np.sin(th) * u[:, 1]) > .1
        for ox, oy, orr in others:
            w = np.array([ox, oy]) - P
            proj = w[:, 0] * u[:, 0] + w[:, 1] * u[:, 1]
            perp = np.abs(w[:, 0] * u[:, 1] - w[:, 1] * u[:, 0])
            ok &= ~((proj > 0) & (proj < d) & (perp < orr))
        seen |= ok
    return int(seen.sum())


def positions(stems, n, kind):
    lo, hi = np.percentile(stems[:, :2], 10, axis=0), np.percentile(stems[:, :2], 90, axis=0)
    g = np.array([(lo[0] + (i + .5) * (hi[0] - lo[0]) / 5, lo[1] + (j + .5) * (hi[1] - lo[1]) / 5)
                  for i in range(5) for j in range(5)])
    c = (lo + hi) / 2
    if kind == "eng":
        sel = list(np.argsort(np.hypot(*(g - c).T))[:n])
    else:
        sel = [int(np.argmin(np.hypot(*(g - c).T)))]
        while len(sel) < n:
            dd = np.min(np.hypot(g[:, None, 0] - g[None, sel, 0], g[:, None, 1] - g[None, sel, 1]), axis=1)
            sel.append(int(np.argmax(dd)))
    sp = g[sel].copy()
    for k in range(len(sp)):                       # nicht in einem Stamm stehen
        for cx, cy, r in stems:
            dd = np.hypot(sp[k, 0] - cx, sp[k, 1] - cy)
            if dd < r + .4:
                sp[k] = np.array([cx, cy]) + (sp[k] - [cx, cy]) * (r + .45) / max(dd, 1e-6)
    return sp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("laz"); ap.add_argument("ini"); ap.add_argument("--out", required=True)
    ap.add_argument("--voxel", type=float, default=0.02)
    ap.add_argument("--work", default="work3dfin")
    a = ap.parse_args()
    import laspy
    L = laspy.read(a.laz)
    xyz = np.stack([L.x, L.y, L.z], 1).astype(np.float64)
    k = np.floor((xyz - xyz.min(0)) / a.voxel).astype(np.int64)
    _, first = np.unique(k, axis=0, return_index=True)
    xyz = xyz[np.sort(first)]
    print(f"{len(L.x):,} Punkte -> {len(xyz):,} nach {a.voxel*100:.0f}-cm-Voxel", flush=True)
    work = Path(a.work)
    ref = run_fin(xyz, a.ini, work / "full")
    print(f"voll: {len(ref)} Staemme, {np.sum(ref[:, 2] > 0)} mit BHD", flush=True)
    # Verdecker = ALLE Detektionen der vollen Wolke; ohne 3DFin-BHD Radius per Kasa-Fit
    # der Punkte 1,0-1,6 m ueber dem lokalen Tiefpunkt (sonst 15 cm)
    from scipy.spatial import cKDTree
    tree = cKDTree(xyz[:, :2]); occ = []
    for x, y, dcm in ref:
        r = dcm / 200
        if not (.035 <= r <= .75):
            P = xyz[tree.query_ball_point([x, y], .6)]
            r = .15
            if len(P) > 50:
                z0 = np.percentile(P[:, 2], 1); sl = P[(P[:, 2] >= z0 + 1.0) & (P[:, 2] <= z0 + 1.6)]
                if len(sl) > 30:
                    A = np.c_[2 * sl[:, 0], 2 * sl[:, 1], np.ones(len(sl))]
                    c = np.linalg.lstsq(A, (sl[:, :2] ** 2).sum(1), rcond=None)[0]
                    rr = np.sqrt(c[2] + c[0] ** 2 + c[1] ** 2)
                    if .035 <= rr <= .75 and np.hypot(c[0] - x, c[1] - y) < .4:
                        r = rr; x, y = c[0], c[1]
        occ.append((x, y, r))
    occ = np.array(occ)
    isref = (ref[:, 2] >= 7) & (ref[:, 2] <= 150)            # Referenz = Staemme mit 3DFin-BHD
    if isref.sum() < 3:
        sys.exit("zu wenige Referenzstaemme")
    stems = occ
    rows = []
    cfgs = [("raster", n) for n in NS] + [("eng", 4)]
    for lay, n in cfgs:
        sps = positions(stems[isref], n, lay)
        keep = np.zeros(len(xyz), bool)
        for sp in sps:
            keep |= visible_points(xyz[:, :2], sp, stems)
        det = run_fin(xyz[keep], a.ini, work / f"{lay}{n}")
        print(f"{lay} n={n}: {keep.mean():.0%} der Punkte, {len(det)} Detektionen", flush=True)
        used = set()
        for i, (cx, cy, r) in enumerate(stems):
            if not isref[i]:
                continue
            r = ref[i, 2] / 200; cx, cy = ref[i, 0], ref[i, 1]
            row = {"plot": Path(a.laz).stem, "layout": lay, "n_scans": n, "stem": i, "x": round(cx, 2), "y": round(cy, 2),
                   "ref_dbh_cm": round(200 * r, 1), "arc_geo_deg": arc_visible(stems, i, sps),
                   "pts_kept": round(float(keep.mean()), 3), "detected": 0, "fin_dbh_cm": ""}
            if len(det):
                dd = np.hypot(det[:, 0] - cx, det[:, 1] - cy); j = int(np.argmin(dd))
                if dd[j] <= .5:
                    row["detected"] = 1; row["fin_dbh_cm"] = round(float(det[j, 2]), 1); used.add(j)
            rows.append(row)
        rows.append({"plot": Path(a.laz).stem, "layout": lay, "n_scans": n, "stem": -1, "x": "", "y": "",
                     "ref_dbh_cm": "", "arc_geo_deg": "", "pts_kept": round(float(keep.mean()), 3),
                     "detected": len(det) - len(used), "fin_dbh_cm": ""})   # stem -1: unzugeordnete Detektionen
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {int(isref.sum())} Referenzstaemme, {len(rows)} Zeilen")


if __name__ == "__main__":
    main()
