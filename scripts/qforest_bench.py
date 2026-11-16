#!/usr/bin/env python3
"""qforest_bench.py -- Q-ForestLab-Benchmark (Instanz-Ground-Truth) fuer die Suite.

Datensatz: Cherlet et al. (2026), "TLS forest instance segmentation benchmark:
2983 manually segmented trees from four plots", Zenodo 16875688, CC BY 4.0
(Q-ForestLab, Universitaet Gent). Vier Plots, RIEGL VZ, jeder Punkt traegt
'semantic' (0 Boden, 1 Baum) und 'instance' (Baum-ID, -1 Boden) -- manuell von
neun Bearbeitern segmentiert, von einer Person nachkontrolliert.

Bisher hatte die Suite Ground Truth nur fuer Klassen (SegmentedForests) oder fuer
einzelne Baeume (Hecken, SYSSIFOSS). Hier ist zum ersten Mal JEDER Baum eines
Plots als Instanz bekannt. Damit lassen sich beide Schritte der Kette messen:

  1. Stammdetektion  (Recall/Precision gegen die Referenzstaemme)
  2. Einzelbaum-Segmentierung (ITCD, itcd_cloud.py) -- IoU je Referenzbaum

Unterbefehle:

  prep  PLY -> Analyse-.npz (xyz relativ zu shift, Instanz, Semantik, 2-cm-Voxel)
  gt    Referenzbaeume aus den Instanzen: Position und BHD in 1,3 m, Hoehe,
        Kronenmaße -> CSV
  las   .npz -> LAS fuer 3DFin (ohne Labels -- der Detektor sieht keine Wahrheit)
  fin   3DFin mit INI auf der Wolke -> Stammliste (CSV wie inventory_from_cloud.py)
  eval  Detektionen (+ optional ITCD-Labels) gegen die Referenz -> JSON-Bericht

  python scripts/qforest_bench.py prep robsoncreek_test.ply --out data/qforest/rc_test.npz
  python scripts/qforest_bench.py gt   data/qforest/rc_test.npz --out data/qforest/rc_gt.csv
  python scripts/qforest_bench.py fin  data/qforest/rc_test.npz extdata/qforest/robsoncreek.ini \\
         --out data/qforest/rc_3dfin.csv --work data/qforest/work
  python scripts/qforest_bench.py eval data/qforest/rc_test.npz data/qforest/rc_gt.csv \\
         --det 3DFin=data/qforest/rc_3dfin.csv --det Baseline=data/qforest/rc_base.csv \\
         --itcd data/qforest/rc_itcd.npz --out data/qforest/rc_report.json
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from inventory_from_cloud import fit_circle                      # noqa: E402

GROUND_CELL = 1.0
BH_LO, BH_HI = 1.0, 1.6        # Brusthoehen-Band ueber Boden [m]
MIN_DBH_CM = 10.0              # Kluppschwelle fuer die Kennzahlen (wie im Feld)


# --------------------------------------------------------------------------- IO
def read_ply(path):
    """Binaeres PLY (little endian) mit beliebigen Skalarfeldern -> dict of arrays."""
    types = {"float": "<f4", "float32": "<f4", "double": "<f8", "float64": "<f8",
             "int": "<i4", "int32": "<i4", "uint": "<u4", "uint32": "<u4",
             "short": "<i2", "int16": "<i2", "ushort": "<u2", "uint16": "<u2",
             "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1"}
    with open(path, "rb") as fh:
        if fh.readline().strip() != b"ply":
            raise SystemExit(f"{path}: kein PLY")
        n, props, fmt = 0, [], None
        while True:
            line = fh.readline().decode("ascii", "replace").strip()
            if line == "end_header":
                break
            p = line.split()
            if not p:
                continue
            if p[0] == "format":
                fmt = p[1]
            elif p[0] == "element" and p[1] == "vertex":
                n = int(p[2])
            elif p[0] == "property" and p[1] != "list":
                props.append((p[2], types[p[1]]))
        if fmt != "binary_little_endian":
            raise SystemExit(f"{path}: Format {fmt} nicht unterstuetzt")
        data = np.fromfile(fh, dtype=np.dtype(props), count=n)
    return {k: data[k] for k, _ in props}


def ground_from_points(gxyz, cell=GROUND_CELL):
    """Bodenraster aus Bodenpunkten: Zelle -> Median-z; Luecken per Nachbarzelle."""
    ix = np.floor(gxyz[:, 0] / cell).astype(np.int64)
    iy = np.floor(gxyz[:, 1] / cell).astype(np.int64)
    x0, y0 = ix.min(), iy.min()
    W, H = ix.max() - x0 + 1, iy.max() - y0 + 1
    s = np.zeros((W, H)); c = np.zeros((W, H))
    np.add.at(s, (ix - x0, iy - y0), gxyz[:, 2])
    np.add.at(c, (ix - x0, iy - y0), 1)
    g = np.where(c > 0, s / np.maximum(c, 1), np.nan)
    for _ in range(50):                                 # Luecken schliessen
        if not np.isnan(g).any():
            break
        pad = np.pad(g, 1, constant_values=np.nan)
        nb = np.stack([pad[1:-1, :-2], pad[1:-1, 2:], pad[:-2, 1:-1], pad[2:, 1:-1]])
        fill = np.nanmean(np.where(np.isnan(nb), np.nan, nb), axis=0) \
            if np.isfinite(nb).any() else g
        g = np.where(np.isnan(g), fill, g)
    g = np.where(np.isnan(g), np.nanmedian(g), g)

    def at(x, y):
        jx = np.clip(np.floor(x / cell).astype(np.int64) - x0, 0, W - 1)
        jy = np.clip(np.floor(y / cell).astype(np.int64) - y0, 0, H - 1)
        return g[jx, jy]
    return at


def voxel_keep(xyz, v):
    """Index eines Punktes je belegtem Voxel (erster Treffer)."""
    k = np.floor(xyz / v).astype(np.int64)
    k -= k.min(0)
    key = (k[:, 0] * (k[:, 1].max() + 1) + k[:, 1]) * (k[:, 2].max() + 1) + k[:, 2]
    _, idx = np.unique(key, return_index=True)
    return np.sort(idx)


# ------------------------------------------------------------------------- prep
def cmd_prep(a):
    d = read_ply(a.ply)
    xyz = np.stack([d["x"], d["y"], d["z"]], 1).astype(np.float64)
    inst = d["instance"].astype(np.int32)
    sem = d["semantic"].astype(np.int8)
    print(f"{len(xyz):,} Punkte, {len(np.unique(inst[inst > 0]))} Instanzen, "
          f"Boden {100 * (sem == 0).mean():.1f}%")
    if a.voxel > 0:
        keep = voxel_keep(xyz, a.voxel)
        xyz, inst, sem = xyz[keep], inst[keep], sem[keep]
        print(f"  {a.voxel * 100:.0f}-cm-Voxel: {len(xyz):,} Punkte")
    shift = np.floor(xyz.min(0))
    loc = (xyz - shift).astype(np.float32)
    at = ground_from_points(xyz[sem == 0])
    hag = (xyz[:, 2] - at(xyz[:, 0], xyz[:, 1])).astype(np.float32)
    rgb = height_rgb(hag, sem)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    np.savez(a.out, xyz=loc, shift=shift, inst=inst, sem=sem, hag=hag, rgb=rgb)
    print(f"-> {a.out}  (Hoehe ueber Boden aus den Bodenpunkten des Datensatzes)")


def height_rgb(hag, sem):
    """Grundeinfaerbung ohne Kamerafarbe: Boden erdfarben, Vegetation nach Hoehe."""
    stops = np.array([[52, 92, 58], [70, 140, 70], [140, 190, 85], [225, 225, 140]], float)
    t = np.clip(hag / max(np.percentile(hag[sem != 0], 99), 1.0), 0, 1) * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    f = (t - i)[:, None]
    rgb = stops[i] * (1 - f) + stops[i + 1] * f
    rgb[sem == 0] = (118, 100, 82)
    return rgb.astype(np.uint8)


def load(npz):
    d = np.load(npz)
    return (d["xyz"].astype(np.float64) + d["shift"], d["inst"], d["sem"], d["hag"])


# --------------------------------------------------------------------------- gt
def crown_metrics(pts, hag):
    """Kronenansatz/-laenge/-durchmesser/-volumen aus dem Radiusprofil (wie seed_hedgerow)."""
    top = float(hag.max())
    if top < 3.0:
        return {}
    sl = pts[(hag >= BH_LO) & (hag <= BH_HI)]
    cx, cy = (sl[:, :2].mean(0) if len(sl) else pts[:, :2].mean(0))
    rad = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    nb = max(6, int(top / 0.5))
    edges = np.linspace(0, top, nb + 1)
    idx = np.clip(np.digitize(hag, edges) - 1, 0, nb - 1)
    r90 = np.array([np.percentile(rad[idx == b], 90) if (idx == b).sum() >= 8 else 0.0
                    for b in range(nb)])
    rmax = float(r90.max())
    if rmax < 0.5:
        return {}
    wide = [b for b in range(nb) if r90[b] >= 0.35 * rmax and edges[b] >= 1.3]
    if not wide:
        return {}
    cbh = float(edges[wide[0]])
    cp = pts[hag >= cbh]
    k = np.floor(cp / 0.3).astype(np.int64)
    nvox = len(np.unique(k[:, 0] * 73856093 ^ k[:, 1] * 19349663 ^ k[:, 2] * 83492791))
    return {"Kronenansatz_m": round(cbh, 1), "Kronenlaenge_m": round(top - cbh, 1),
            "Kronendurchmesser_m": round(2 * rmax, 1),
            "Kronenvolumen_m3": round(nvox * 0.027, 1)}


def robust_circle(px, py, it=4):
    """Kreisfit mit iterativem Ausschluss von Ausreissern (Blaetter, Aeste, Wurzelanlauf).

    Ein einzelner Kasa-Fit ueber die ganze Brusthoehen-Scheibe zieht bei jungen
    Regenwaldbaeumen das Laub mit hinein (RMS 4-10 cm). Nach drei Runden mit
    Schwelle 2,5 x Median-Residuum bleibt der Stammring uebrig.
    """
    m = np.ones(len(px), bool)
    for _ in range(it):
        if m.sum() < 20:
            return None
        f = fit_circle(px[m], py[m])
        if not f:
            return None
        cx, cy, r, rms, arc = f
        res = np.abs(np.hypot(px - cx, py - cy) - r)
        m = res <= max(0.015, 2.5 * float(np.median(res[m])))
    if m.sum() < 20:
        return None
    f = fit_circle(px[m], py[m])
    return (*f, float(m.mean())) if f else None


def cmd_gt(a):
    xyz, inst, sem, hag = load(a.npz)
    lo_xy, hi_xy = xyz[:, :2].min(0), xyz[:, :2].max(0)
    order = np.argsort(inst, kind="stable")
    ids, start = np.unique(inst[order], return_index=True)
    bounds = list(start[1:]) + [len(order)]
    rows = []
    for tid, lo, hi in zip(ids, start, bounds):
        if tid <= 0:
            continue
        sel = order[lo:hi]
        p, h = xyz[sel], hag[sel]
        r = {"id": int(tid), "Punkte": int(len(sel)), "Hoehe_m": round(float(h.max()), 1)}
        sl = p[(h >= 1.2) & (h <= 1.4)]                  # schmale Scheibe um 1,3 m
        band = p[(h >= BH_LO) & (h <= BH_HI)]
        ref = sl if len(sl) >= 20 else band
        r["x"], r["y"] = (float(np.median(ref[:, 0])), float(np.median(ref[:, 1]))) \
            if len(ref) else (float(np.median(p[:, 0])), float(np.median(p[:, 1])))
        r["z"] = float(p[:, 2][np.argmin(h)] - h.min())     # Bodenhoehe am Stammfuss
        # Randbaum: Stamm ausserhalb der Testflaeche oder vom Flaechenrand angeschnitten
        # -- zaehlt weder als Referenz noch als Fehlalarm, wenn ein Detektor ihn trifft
        edge = len(band) < 20 or bool(
            (band[:, :2].min(0) - lo_xy < 0.25).any() or (hi_xy - band[:, :2].max(0) < 0.25).any())
        r["Rand"] = "ja" if edge else "nein"
        r["BHD_cm"], r["BHD_Guete"] = "", ("Stamm ausserhalb/am Rand der Testflaeche"
                                           if edge else "zu wenige Punkte in 1,2-1,4 m")
        if not edge and len(sl) >= 20:
            fit = robust_circle(sl[:, 0], sl[:, 1])
            if fit:
                cx, cy, rr, rms, arc, keep = fit
                ok = 0.02 <= rr <= 2.5 and arc >= 150 and rms <= max(0.02, 0.1 * rr) and keep >= 0.5
                # Schaftkontrolle: setzt sich der Stamm bei 2,0 m mit aehnlichem
                # Durchmesser fort? Unterstand-Baeumchen mit Laub bis zum Boden
                # liefern in 1,3 m oft einen "Ring" aus Blaettern (bis 1,5 m), der
                # bei 2,0 m nicht wiederkehrt.
                up = p[(h >= 1.9) & (h <= 2.1)]
                f2 = robust_circle(up[:, 0], up[:, 1]) if ok and len(up) >= 20 else None
                cont = bool(f2 and f2[3] <= max(0.02, 0.1 * f2[2])
                            and abs(f2[2] - rr) <= max(0.015, 0.2 * rr))
                if ok and cont:
                    r["x"], r["y"] = float(cx), float(cy)
                    r["BHD_cm"] = round(2 * rr * 100, 1)
                    r["BHD_Guete"] = "gut" if rms <= max(0.01, 0.06 * rr) else "maessig"
                elif ok:
                    r["BHD_Guete"] = ("Schaftkontrolle verworfen: in 2,0 m kein passender "
                                      "Stammquerschnitt (Laub/Aeste in Brusthoehe?)")
                else:
                    r["BHD_Guete"] = (f"Kreisfit verworfen (Bogen {arc:.0f} Grad, "
                                      f"RMS {rms * 100:.1f} cm) -- Brettwurzel, Schraeglage "
                                      f"oder Aeste in Brusthoehe")
        r.update(crown_metrics(p, h))
        rows.append(r)
    fields = ["id", "x", "y", "z", "Rand", "BHD_cm", "BHD_Guete", "Hoehe_m", "Punkte",
              "Kronenansatz_m", "Kronenlaenge_m", "Kronendurchmesser_m", "Kronenvolumen_m3"]
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    nb = sum(1 for r in rows if r["BHD_cm"] != "")
    ne = sum(1 for r in rows if r["Rand"] == "ja")
    print(f"-> {a.out}: {len(rows)} Referenzbaeume ({ne} am Rand), BHD fuer {nb}")


def is_reference(r):
    """Zaehlt fuer Recall: Stamm im Plot und BHD >= 10 cm -- oder ohne messbaren BHD
    ab 10 m Hoehe (Brettwurzel/Schraeglage: sicher ein Baum, nur kein Kreis in 1,3 m).

    Niedrigere Baeume ohne messbaren BHD bleiben draussen: im Regenwald-Unterstand
    sind das fast immer Baeumchen mit Laub bis zum Boden (Spannweite in 1,3 m bis
    2 m) -- dort gibt es keinen Stamm zu detektieren, ein Fehlschlag waere unfair.
    """
    if r.get("Rand") == "ja":
        return False
    if r["BHD_cm"]:
        return float(r["BHD_cm"]) >= MIN_DBH_CM
    return float(r["Hoehe_m"]) >= 10.0


# ---------------------------------------------------------------------- las/fin
def write_las(xyz, path):
    import laspy
    off = np.floor(xyz.min(0))
    hdr = laspy.LasHeader(point_format=3)
    hdr.offsets = [0.0] * 3
    hdr.scales = [0.001] * 3
    las = laspy.LasData(hdr)
    loc = xyz - off
    las.x, las.y, las.z = loc[:, 0], loc[:, 1], loc[:, 2]
    las.write(str(path))
    return off


def cmd_fin(a):
    import configparser
    from three_d_fin.processing.configuration import FinConfiguration
    from three_d_fin.processing.standalone_processing import StandaloneLASProcessing
    xyz, *_ = load(a.npz)
    work = Path(a.work)
    work.mkdir(parents=True, exist_ok=True)
    off = write_las(xyz, work / "plot.las")
    cp = configparser.ConfigParser()
    cp.read(a.ini)
    if cp.has_section("misc"):
        cp.remove_section("misc")
    with open(work / "fin.ini", "w") as fh:
        cp.write(fh)
    cfg = FinConfiguration.From_config_file(work / "fin.ini", init_misc=True)
    copy = lambda o, **u: (getattr(o, "model_copy", None) or o.copy)(update=u)  # noqa: E731
    misc = copy(cfg.misc, input_file=work / "plot.las", output_dir=work,
                is_normalized=False, is_noisy=True, export_txt=True)
    StandaloneLASProcessing(copy(cfg, misc=misc)).process()
    rows = []
    for i, line in enumerate((work / "plot_dbh_and_heights.txt").read_text().splitlines(), 1):
        p = line.split()
        try:
            h, d, x, y = float(p[0]), float(p[1]), float(p[2]), float(p[3])
        except (IndexError, ValueError):
            continue
        rows.append({"label": f"3dfin {i:03d}", "x": round(x + off[0], 3),
                     "y": round(y + off[1], 3), "BHD_cm": round(d * 100, 1) if d > 0 else "",
                     "Hoehe_m": round(h, 1)})
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["label", "x", "y", "BHD_cm", "Hoehe_m"])
        w.writeheader()
        w.writerows(rows)
    print(f"-> {a.out}: {len(rows)} Staemme")


# ------------------------------------------------------------------------- eval
def read_stems(path):
    out = []
    for r in csv.DictReader(open(path, encoding="utf-8-sig")):
        try:
            out.append((float(r["x"]), float(r["y"]),
                        float(r["BHD_cm"]) if r.get("BHD_cm") else float("nan")))
        except (KeyError, ValueError):
            continue
    return np.array(out).reshape(-1, 3)


def match(gt, det, base_dist):
    """Greedy-Zuordnung nach Abstand; Schwelle je Referenz max(base, Radius)."""
    pairs = []
    if len(det):
        for i, (gx, gy, gd) in enumerate(gt):
            dd = np.hypot(det[:, 0] - gx, det[:, 1] - gy)
            thr = max(base_dist, (gd / 200.0) if np.isfinite(gd) else 0.0)
            for j in np.flatnonzero(dd <= thr):
                pairs.append((dd[j], i, j))
    pairs.sort()
    gi, dj, m = set(), set(), []
    for d, i, j in pairs:
        if i in gi or j in dj:
            continue
        gi.add(i); dj.add(j); m.append((i, j, d))
    return m


def cmd_eval(a):
    xyz, inst, sem, hag = load(a.npz)
    gtr = list(csv.DictReader(open(a.gt, encoding="utf-8")))
    gt = np.array([(float(r["x"]), float(r["y"]),
                    float(r["BHD_cm"]) if r["BHD_cm"] else float("nan")) for r in gtr])
    # Referenz fuer die Kennzahlen: siehe is_reference()
    big = np.array([is_reference(r) for r in gtr])
    rep = {"referenz": {"baeume_gesamt": len(gt), "baeume_ab_10cm": int(big.sum()),
                        "kluppschwelle_cm": MIN_DBH_CM,
                        "randbaeume": sum(1 for r in gtr if r.get("Rand") == "ja"),
                        "regel": ("Stamm in der Testflaeche und BHD >= 10 cm; ohne messbaren "
                                  "BHD (Brettwurzel, Schraeglage) zaehlt der Baum ab 10 m "
                                  "Hoehe mit. Randbaeume zaehlen weder als Referenz noch "
                                  "als Fehlalarm.")},
           "match_dist_m": a.match_dist, "detektion": {}, "per_tree": {}}
    gsel = np.flatnonzero(big)
    xmin, ymin = xyz[:, 0].min(), xyz[:, 1].min()
    xmax, ymax = xyz[:, 0].max(), xyz[:, 1].max()
    for spec in a.det or []:
        name, path = spec.split("=", 1)
        det = read_stems(path)
        # nur Detektionen innerhalb der Testflaeche (Randstreifen 0,5 m)
        ins = ((det[:, 0] > xmin + .5) & (det[:, 0] < xmax - .5) &
               (det[:, 1] > ymin + .5) & (det[:, 1] < ymax - .5)) if len(det) else []
        det = det[ins] if len(det) else det
        m_all = match(gt, det, a.match_dist)
        hit_gt = {i: (j, d) for i, j, d in m_all}
        tp = sum(1 for i in gsel if i in hit_gt)
        # Fehlalarm = Detektion, die auf KEINEN Referenzbaum passt (auch keinen kleinen)
        fp = len(det) - len(m_all)
        err = [det[hit_gt[i][0], 2] - gt[i, 2] for i in gsel
               if i in hit_gt and np.isfinite(gt[i, 2]) and np.isfinite(det[hit_gt[i][0], 2])]
        err = np.array(err)
        rep["detektion"][name] = {
            "detektionen": int(len(det)), "treffer": int(tp),
            "recall": round(tp / max(len(gsel), 1), 3),
            "precision": round(len(m_all) / max(len(det), 1), 3),
            "fehlalarme": int(fp),
            "bhd_bias_cm": round(float(err.mean()), 1) if len(err) else None,
            "bhd_rmse_cm": round(float(np.sqrt((err ** 2).mean())), 1) if len(err) else None,
            "bhd_n": int(len(err)),
            "lagefehler_median_cm": (round(float(np.median([d for i, j, d in m_all])) * 100, 1)
                                     if m_all else None)}
        rep["per_tree"][name] = {gtr[i]["id"]: {"gefunden": i in hit_gt,
                                               "bhd_cm": (None if i not in hit_gt or not
                                                          np.isfinite(det[hit_gt[i][0], 2])
                                                          else round(float(det[hit_gt[i][0], 2]), 1))}
                                 for i in range(len(gt))}
        print(f"{name}: {len(det)} Detektionen, Recall {tp}/{len(gsel)} = "
              f"{tp / max(len(gsel), 1):.1%}, Precision {len(m_all) / max(len(det), 1):.1%}"
              + (f", BHD-RMSE {rep['detektion'][name]['bhd_rmse_cm']} cm (n={len(err)})"
                 if len(err) else ""))

    if a.itcd:
        d = np.load(a.itcd, allow_pickle=True)
        lab = d["label"]
        if len(lab) != len(inst):
            raise SystemExit(f"ITCD-Labels {len(lab)} != Wolke {len(inst)}")
        tree = inst > 0
        # Kontingenz Referenz x Segment ueber alle Punkte
        gi = inst.astype(np.int64)
        sj = lab.astype(np.int64) + 1                   # 0 = unzugeordnet
        key = gi * (sj.max() + 1) + sj
        k, cnt = np.unique(key[tree], return_counts=True)
        g_of, s_of = k // (sj.max() + 1), k % (sj.max() + 1)
        gsize = dict(zip(*np.unique(gi[tree], return_counts=True)))
        ssize = dict(zip(*np.unique(sj, return_counts=True)))
        best = {}
        for g, s, c in zip(g_of, s_of, cnt):
            if s == 0:
                continue
            iou = c / (gsize[g] + ssize[s] - c)
            if iou > best.get(int(g), (0, -1))[0]:
                best[int(g)] = (float(iou), int(s) - 1)
        ids_big = [int(gtr[i]["id"]) for i in gsel]
        ious = np.array([best.get(t, (0.0, -1))[0] for t in ids_big])
        rep["itcd"] = {"mittlere_iou": round(float(ious.mean()), 3),
                       "anteil_iou_ab_0_5": round(float((ious >= 0.5).mean()), 3),
                       "n": int(len(ious)),
                       "zugeordnete_baumpunkte": round(float((lab[tree] >= 0).mean()), 3)}
        rep["per_tree"]["ITCD"] = {str(t): {"iou": round(best.get(t, (0.0, -1))[0], 3),
                                            "segment": best.get(t, (0.0, -1))[1]}
                                   for t in (int(r["id"]) for r in gtr)}
        print(f"ITCD: mittlere IoU {ious.mean():.2f}, IoU>=0,5 bei {(ious >= .5).mean():.0%} "
              f"der {len(ious)} Referenzbaeume")
    Path(a.out).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {a.out}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep"); p.add_argument("ply"); p.add_argument("--out", required=True)
    p.add_argument("--voxel", type=float, default=0.02, help="Ausduennung [m], 0 = aus")
    p = sub.add_parser("gt"); p.add_argument("npz"); p.add_argument("--out", required=True)
    p = sub.add_parser("las"); p.add_argument("npz"); p.add_argument("--out", required=True)
    p = sub.add_parser("fin"); p.add_argument("npz"); p.add_argument("ini")
    p.add_argument("--out", required=True); p.add_argument("--work", default="work3dfin")
    p = sub.add_parser("eval"); p.add_argument("npz"); p.add_argument("gt")
    p.add_argument("--det", action="append", help="Name=stems.csv (mehrfach)")
    p.add_argument("--itcd", help="Label-.npz aus itcd_cloud.py (gleiche Punktreihenfolge)")
    p.add_argument("--match-dist", type=float, default=0.6)
    p.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "las":
        xyz, *_ = load(a.npz)
        write_las(xyz, a.out)
        print(f"-> {a.out}")
        return
    {"prep": cmd_prep, "gt": cmd_gt, "fin": cmd_fin, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
