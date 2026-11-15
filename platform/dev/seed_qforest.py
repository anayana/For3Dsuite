#!/usr/bin/env python3
"""seed_qforest.py -- Q-ForestLab-Benchmark-Plot als begehbare Suite-Szene.

Quelle: Cherlet et al. (2026), TLS forest instance segmentation benchmark,
Zenodo 16875688, CC BY 4.0 (Q-ForestLab, Universitaet Gent). Jeder Punkt traegt
die manuell vergebene Baum-ID -- die Szene zeigt deshalb drei Einfaerbungen
derselben Geometrie:

    Hoehe         |  Ground Truth (Baum-Instanzen)  |  Einzelbaeume (unsere ITCD)

Der Datensatz hat keine Kamerafarbe; die Grundeinfaerbung ist die Hoehe ueber
Boden (pointcloud.base_label = "Höhe"). Die ITCD-Segmente tragen die Farbe des
Referenzbaums, den sie am besten treffen: gleiche Farbe beim Umschalten heisst
"richtig getrennt", ein Farbwechsel innerhalb eines Baumes zeigt Fehler.
Zerfaellt ein Baum in mehrere Segmente, bekommt nur das beste seine Farbe.

Eingaben aus scripts/qforest_bench.py (prep, gt, fin, eval) und itcd_cloud.py:

  python platform/dev/seed_qforest.py qforest-robsoncreek data/qforest/rc_test.npz \\
      data/qforest/rc_gt.csv data/qforest/rc_report.json --itcd data/qforest/rc_itcd.npz \\
      --title "..." --plot-info "..." --lat -17.12 --lon 145.63
"""
import argparse
import colorsys
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
MEDIA = REPO / "platform" / "dev-data" / "media"
sys.path.insert(0, str(REPO / "scripts"))
from qforest_bench import is_reference                            # noqa: E402
LEVELS = [("lite", "Ausgedünnt", "cloud_lite.bin", 160_000),
          ("full", "Voll", "cloud.bin", 700_000)]
GROUND = (118, 100, 82)
UNASSIGNED = (95, 98, 104)


def inst_color(i):
    """Feste, gut unterscheidbare Farbe je Baum-ID (Goldener-Schnitt-Farbton)."""
    h = (i * 0.6180339887) % 1.0
    s = 0.55 + 0.35 * ((i * 7) % 3) / 2
    v = 0.80 + 0.18 * ((i * 11) % 2)
    return tuple(int(c * 255) for c in colorsys.hsv_to_rgb(h, s, v))


def itcd_colors(inst, lab):
    """Segment -> Farbe: die des Referenzbaums mit der hoechsten IoU, sonst eigene."""
    tree = inst > 0
    gi = inst.astype(np.int64)
    sj = lab.astype(np.int64) + 1
    M = sj.max() + 1
    k, cnt = np.unique((gi * M + sj)[tree & (sj > 0)], return_counts=True)
    g_of, s_of = k // M, k % M
    gsize = dict(zip(*np.unique(gi[tree], return_counts=True)))
    ssize = dict(zip(*np.unique(sj, return_counts=True)))
    best_for_tree = {}                       # Baum -> (iou, segment)
    major = {}                               # Segment -> (punkte, baum)
    for g, s, c in zip(g_of, s_of, cnt):
        iou = c / (gsize[g] + ssize[s] - c)
        if iou > best_for_tree.get(g, (0, 0))[0]:
            best_for_tree[g] = (iou, s)
        if c > major.get(s, (0, 0))[0]:
            major[s] = (c, g)
    col = {}
    for g, (iou, s) in best_for_tree.items():
        if major.get(s, (0, -1))[1] == g:    # Segment gehoert wirklich zu diesem Baum
            col[s] = inst_color(int(g))
    lut = np.empty((M, 3), np.uint8)
    lut[:] = UNASSIGNED
    for s in range(1, M):
        lut[s] = col.get(s, inst_color(100_000 + s))
    return lut[sj]


def thumbnail(dest, p, hag, rgb, inst, W=640, H=480):
    """Seitenansicht maßstabstreu, y = Hoehe ueber Boden (Hang flachgelegt),
    Baeume in Instanzfarbe, Boden als schmales Band."""
    img = np.full((H, W, 3), 13, np.uint8)
    pad = 12
    sc = min((W - 2 * pad) / max(np.ptp(p[:, 0]), 1e-6),
             (H - 2 * pad) / max(float(hag.max()) + 0.5, 1e-6))
    order = np.argsort(p[:, 1])[::-1]               # hintere Punkte zuerst
    x0 = (W - sc * np.ptp(p[:, 0])) / 2
    nx = (x0 + (p[order, 0] - p[:, 0].min()) * sc).astype(int)
    ny = (H - pad - np.maximum(hag[order], 0) * sc).astype(int)
    c = rgb[order]
    for dx in (0, 1):
        for dy in (0, 1):
            img[np.clip(ny + dy, 0, H - 1), np.clip(nx + dx, 0, W - 1)] = c
    Image.fromarray(img).save(dest, quality=82)


def start_view(lv):
    """Startkamera von Suedwesten, schraeg von oben: der ganze Bestand im Bild."""
    mn, mx = np.array(lv["bbox_min"]), np.array(lv["bbox_max"])
    c = (mn + mx) / 2
    span = float(max(mx[0] - mn[0], mx[1] - mn[1], (mx[2] - mn[2]) * 0.8))
    pos = [c[0] - 0.85 * span, c[1] - 1.1 * span, mn[2] + 0.55 * (mx[2] - mn[2])]
    target = [c[0], c[1], mn[2] + 0.4 * (mx[2] - mn[2])]
    return {"pos": [round(float(v), 2) for v in pos],
            "target": [round(float(v), 2) for v in target]}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sid")
    ap.add_argument("npz")
    ap.add_argument("gt")
    ap.add_argument("report")
    ap.add_argument("--itcd")
    ap.add_argument("--title", required=True)
    ap.add_argument("--plot-info", required=True)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--detector", default="3DFin")
    args = ap.parse_args()

    d = np.load(args.npz)
    xyz = d["xyz"].astype(np.float64) + d["shift"]
    inst, sem, rgb = d["inst"], d["sem"], d["rgb"]
    rep = json.loads(Path(args.report).read_text(encoding="utf-8"))
    gtr = list(csv.DictReader(open(args.gt, encoding="utf-8")))
    lab = np.load(args.itcd, allow_pickle=True)["label"] if args.itcd else None

    origin = np.array([xyz[:, 0].mean(), xyz[:, 1].mean(), np.percentile(xyz[:, 2], 1)])
    local = (xyz - origin).astype(np.float32)
    gt_rgb = np.array([inst_color(int(i)) for i in range(int(inst.max()) + 1)], np.uint8)
    gt_rgb = np.where((inst > 0)[:, None], gt_rgb[np.maximum(inst, 0)], np.uint8(GROUND))
    seg_rgb = None
    if lab is not None:
        seg_rgb = itcd_colors(inst, lab)
        seg_rgb[(lab < 0) & (sem == 0)] = GROUND

    dest = MEDIA / "scenes" / args.sid
    dest.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    levels = []
    for lid, label, fname, maxpts in LEVELS:
        sel = (np.sort(rng.choice(len(local), maxpts, replace=False))
               if len(local) > maxpts else np.arange(len(local)))
        p = np.ascontiguousarray(local[sel], "<f4")
        (dest / fname).write_bytes(p.tobytes() + rgb[sel].tobytes())
        lv = {"id": lid, "label": label, "bin": f"scenes/{args.sid}/{fname}",
              "count": int(len(p)),
              "bbox_min": [float(v) for v in p.min(0)],
              "bbox_max": [float(v) for v in p.max(0)]}
        gname = fname.replace(".bin", "_gt.bin")
        (dest / gname).write_bytes(p.tobytes() + gt_rgb[sel].tobytes())
        lv["bin_gt"] = f"scenes/{args.sid}/{gname}"
        if seg_rgb is not None:
            sname = fname.replace(".bin", "_seg.bin")
            (dest / sname).write_bytes(p.tobytes() + seg_rgb[sel].tobytes())
            lv["bin_itcd"] = f"scenes/{args.sid}/{sname}"
        levels.append(lv)
        print(f"  {label}: {len(p):,} Punkte")
        if lid == "full":
            thumbnail(dest / "thumb.jpg", local[sel], d["hag"][sel], gt_rgb[sel], inst[sel])

    det = rep["detektion"].get(args.detector, {})
    per = rep.get("per_tree", {})
    markers = []
    for r in gtr:
        if not is_reference(r):          # Marker = genau die Referenz des Benchmarks
            continue
        dbh = float(r["BHD_cm"]) if r["BHD_cm"] else None
        h = float(r["Hoehe_m"])
        x, y, z0 = float(r["x"]), float(r["y"]), float(r["z"])
        attrs = {"Referenz_ID": int(r["id"])}
        if dbh is not None:
            attrs["BHD_cm"] = dbh
        attrs["BHD_Guete"] = r["BHD_Guete"]
        attrs["Hoehe_m"] = h
        for k in ("Kronenansatz_m", "Kronenlaenge_m", "Kronendurchmesser_m",
                  "Kronenvolumen_m3"):
            if r.get(k):
                attrs[k] = float(r[k])
        attrs["Punkte"] = int(r["Punkte"])
        f = per.get(args.detector, {}).get(r["id"])
        if f is not None:
            attrs[f"{args.detector}"] = ("gefunden" + (f" (BHD {f['bhd_cm']} cm)"
                                                       if f.get("bhd_cm") else "")
                                         if f["gefunden"] else "nicht gefunden")
        it = per.get("ITCD", {}).get(r["id"])
        if it is not None:
            attrs["ITCD_IoU"] = it["iou"]
        dx, dy, dz = x - origin[0], y - origin[1], (z0 + 1.3) - origin[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
        markers.append({
            "id": f"t{int(r['id']):04d}", "label": f"Referenzbaum {r['id']}",
            "yaw": round(math.degrees(math.atan2(dy, dx)), 3),
            "pitch": round(math.degrees(math.asin(dz / dist)), 3),
            "xyz": [round(x, 3), round(y, 3), round(z0 + 1.3, 3)],
            "attributes": attrs, "demo": False})

    ref = rep["referenz"]
    it = rep.get("itcd")
    desc = (f"Terrestrischer Laserscan (RIEGL VZ) aus dem Instanz-Benchmark von "
            f"Q-ForestLab (Universitaet Gent). {args.plot_info} Jeder Punkt traegt "
            f"die manuell vergebene Baum-ID: {ref['baeume_ab_10cm']} Referenzbaeume "
            f"ab 10 cm BHD. Daran gemessen findet {args.detector} "
            f"{det.get('treffer', 0)} ({det.get('recall', 0) * 100:.0f} %) bei "
            f"{det.get('precision', 0) * 100:.0f} % Precision")
    if it:
        desc += (f"; die eigene Einzelbaum-Segmentierung trennt "
                 f"{it['anteil_iou_ab_0_5'] * 100:.0f} % der Baeume mit IoU >= 0,5")
    desc += ". Quelle: Zenodo 16875688, CC BY 4.0."
    scene = {
        "id": args.sid, "title": args.title, "description": desc,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{args.sid}/thumb.jpg",
        "width": None, "height": None, "variants": [],
        "source": {
            "type": "qforest-instance-tls",
            "origin_xyz": [float(c) for c in origin],
            "dataset": ("TLS forest instance segmentation benchmark: 2983 manually "
                        "segmented trees from four plots (Cherlet et al. 2026, "
                        "Q-ForestLab). " + args.plot_info),
            "url": "https://doi.org/10.5281/zenodo.16875688",
            "paper": "https://doi.org/10.1016/j.isprsjprs.2025.10.033",
            "license": "CC-BY-4.0",
        },
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "base_label": "Höhe", "gt_tag": "Einzelbaum-Ground-Truth",
                       "start": start_view(levels[0]),
                       "levels": levels},
        "legend": {
            "title": "Einfärbungen",
            "items": [
                {"label": "Höhe über Boden — der Datensatz hat keine Kamerafarbe",
                 "color": "linear-gradient(90deg,rgb(52,92,58),rgb(140,190,85),rgb(225,225,140))"},
                {"label": "Ground Truth — eine Farbe je Baum, von Hand segmentiert",
                 "color": "linear-gradient(90deg,rgb(230,100,90),rgb(90,160,240),rgb(240,190,80))"},
                {"label": "Boden", "color": "rgb({},{},{})".format(*GROUND)},
            ],
            "note": ("Einzelbäume = eigene Segmentierung (itcd_cloud.py). Gleiche Farbe "
                     "wie in der Ground Truth = Baum richtig getrennt; grau = nicht zugeordnet."),
        },
        "validation": {
            "recall": det.get("recall", 0), "precision": det.get("precision", 0),
            "pos_err_median_cm": det.get("lagefehler_median_cm"),
            "matched": det.get("treffer", 0), "reference_trees": ref["baeume_ab_10cm"],
            "match_dist_m": rep["match_dist_m"],
            "method": (f"Detektor {args.detector}; Referenz = manuell segmentierte Bäume "
                       f"im Testgebiet ab 10 cm BHD (ohne messbaren BHD: ab 10 m Höhe)."
                       + (f" Einzelbaum-Segmentierung: mittlere IoU {it['mittlere_iou']:.2f}."
                          if it else "")),
        },
        "benchmark": {k: v for k, v in rep.items() if k != "per_tree"},
        "markers": markers,
    }
    if args.lat is not None:
        scene["source"]["gps"] = {"lat": args.lat, "lon": args.lon}
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2),
                                     encoding="utf-8")
    print(f"-> Szene '{args.sid}': {len(markers)} Referenzbaum-Marker")


if __name__ == "__main__":
    main()
