#!/usr/bin/env python3
"""stand_inventory.py -- echte Bestandeswerte aus mehreren registrierten E57-TLS.

Fuehrt die 4 co-registrierten Renon-Standpunkte zu EINER dichten Wolke zusammen
(fuellt Scan-Schatten), erkennt Einzelstaemme geometrisch und leitet daraus die
quantitativen Bestandeskennwerte ab -- alles aus den Messdaten, keine Annahmen
ausser Standard-Forstformeln (Volumen-Formfaktor, Reineke-SDI).

Erkennung (dichte stationaere TLS, volle Baumhoehe vorhanden):
  1. Bodenmodell (0,5-m-Raster, 5. Perzentil)
  2. Detektionsband (0,7-2,0 m ueber Boden) -> XY-Cluster (Zusammenhangskomponenten)
  3. Kasa-Kreis-Fit im Messfenster 1,1-1,5 m -> BHD + Stammposition
  4. Plausibilitaet (Radius, Fit-RMS, Bogenabdeckung) + NMS
  5. je Stamm: Hoehe = hoechster Punkt im 1,5-m-Umkreis; Volumen = G*h*Formfaktor

Bestandeswerte (im Plot: Kreis um den Scan-Schwerpunkt, Radius --plot-radius):
  Stammzahl N/ha, Grundflaeche G/ha, Dg (mittl. BHD der Kreisflaeche),
  arithm. mittlerer BHD, Mittelhoehe, Oberhoehe h100, Vorrat V/ha,
  Reineke-SDI, mittlerer Schlankheitsgrad h/d, BHD-Verteilung.

Nutzung:
  python scripts/stand_inventory.py "data/renon/e57/*.e57" viewer/data/renon_stand.json \
      [--plot-radius 15] [--ref-setup 0] [--form-factor 0.5]
"""
import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
from collections import deque

import numpy as np
import pye57

HERE = os.path.dirname(os.path.abspath(__file__))

CELL_GROUND = 0.5
CELL_STEM = 0.04
BH_LO, BH_HI = 0.7, 2.0          # Detektionsband
MEAS_LO, MEAS_HI = 1.1, 1.5      # BHD-Messfenster
R_MIN, R_MAX = 0.03, 0.80        # m Stammradius (BHD 6..160 cm)
FIT_RMS_MAX = 0.03
ARC_MIN_DEG = 80
NMS_DIST = 0.5
MIN_POINTS = 40


def scanner_origin(path):
    """Scanner-Ursprung im gemeinsamen Frame. get_header().translation wirft bei
    manchen pye57-Versionen bad_weak_ptr -> Fallback: Pose-Translation aus der
    (ggf. frisch extrahierten) poses.json des Setups."""
    try:
        return np.asarray(pye57.E57(path).get_header(0).translation, float)
    except Exception:
        pass
    sid = re.search(r"(\d{2,3})", os.path.basename(path)).group(1)
    cands = glob.glob(f"data/renon/extracted*/*{sid}_poses.json")
    if not cands:                                   # noch nicht extrahiert -> nachholen
        d = f"data/renon/extracted_s{sid}"
        subprocess.run([sys.executable, os.path.join(HERE, "e57_extract_images.py"),
                        path, d], check=True, stdout=subprocess.DEVNULL)
        cands = glob.glob(os.path.join(d, "*_poses.json"))
    for pj in cands:
        for e in json.load(open(pj)):
            t = (e.get("pose") or {}).get("translation_xyz")
            if t:
                return np.asarray(t, float)
    raise RuntimeError(f"Kein Ursprung fuer {path}")


def load_merged(files, center_xy, radius):
    """Alle Wolken lesen, auf Plot-Umkreis (+Rand) filtern, zusammenfuehren."""
    xs, ys, zs = [], [], []
    keep_r = radius + 3.0        # etwas Rand fuer Bodenmodell/Hoehe
    for f in files:
        d = pye57.E57(f).read_scan(0, ignore_missing_fields=True)
        x, y, z = d["cartesianX"], d["cartesianY"], d["cartesianZ"]
        m = np.hypot(x - center_xy[0], y - center_xy[1]) <= keep_r
        xs.append(x[m]); ys.append(y[m]); zs.append(z[m])
        print(f"  {f.split(chr(92))[-1].split('/')[-1]}: +{int(m.sum()):,} Punkte im Umkreis")
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(zs)


def ground_model(x, y, z):
    ix = np.floor(x / CELL_GROUND).astype(np.int64)
    iy = np.floor(y / CELL_GROUND).astype(np.int64)
    key = ix * 1_000_003 + iy
    order = np.argsort(key)
    ks, zs = key[order], z[order]
    bounds = np.flatnonzero(np.diff(ks)) + 1
    ground = {}
    for lo, hi in zip(np.r_[0, bounds], np.r_[bounds, len(ks)]):
        if hi - lo >= 15:
            ground[int(ks[lo])] = float(np.percentile(zs[lo:hi], 5))
    return ground, key


def fit_circle(px, py):
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
    arc = float(np.count_nonzero(np.histogram(ang, bins=36, range=(-180, 180))[0])) * 10.0
    return cx, cy, r, rms, arc


def detect_stems(x, y, z, ground, gkey):
    gz = np.array([ground.get(int(k), np.nan) for k in gkey])
    h = z - gz
    sl = (h >= BH_LO) & (h <= BH_HI)
    sx, sy, sh = x[sl], y[sl], h[sl]
    cix = np.floor(sx / CELL_STEM).astype(np.int64)
    ciy = np.floor(sy / CELL_STEM).astype(np.int64)
    cells = {}
    for i, (a, b) in enumerate(zip(cix, ciy)):
        cells.setdefault((int(a), int(b)), []).append(i)
    seen, clusters = set(), []
    for start in cells:
        if start in seen:
            continue
        comp, q = [], deque([start]); seen.add(start)
        while q:
            cell = q.popleft(); comp.append(cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (cell[0]+dx, cell[1]+dy)
                    if nb in cells and nb not in seen:
                        seen.add(nb); q.append(nb)
        idx = np.array([i for cell in comp for i in cells[cell]])
        if len(idx) >= MIN_POINTS:
            clusters.append(idx)

    stems = []
    for idx in clusters:
        sub = idx[(sh[idx] >= MEAS_LO) & (sh[idx] <= MEAS_HI)]
        fit = fit_circle(sx[sub if len(sub) >= 8 else idx], sy[sub if len(sub) >= 8 else idx])
        if fit is None:
            continue
        cx, cy, r, rms, arc = fit
        if not (R_MIN <= r <= R_MAX) or rms > FIT_RMS_MAX or arc < ARC_MIN_DEG:
            continue
        gk = int(np.floor(cx/CELL_GROUND))*1_000_003 + int(np.floor(cy/CELL_GROUND))
        g = ground.get(gk)
        if g is None:
            continue
        near = np.hypot(x - cx, y - cy) <= 1.5
        top = float(z[near].max() - g) if near.any() else float("nan")
        stems.append(dict(x=cx, y=cy, g=g, r=r, rms=rms, arc=arc, n=len(idx), h=top))
    # NMS
    stems.sort(key=lambda s: (-s["n"], s["rms"]))
    kept = []
    for s in stems:
        if all(math.hypot(s["x"]-k["x"], s["y"]-k["y"]) >= NMS_DIST for k in kept):
            kept.append(s)
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("e57"); ap.add_argument("out")
    ap.add_argument("--plot-radius", type=float, default=15.0)
    ap.add_argument("--ref-setup", type=int, default=0, help="Index des Referenz-Setups (Frame-Ursprung)")
    ap.add_argument("--form-factor", type=float, default=0.5)
    args = ap.parse_args()

    files = sorted({f for pat in [args.e57] for f in glob.glob(pat)})
    if not files:
        sys.exit("Keine E57 gefunden.")
    origins = np.array([scanner_origin(f) for f in files])
    center = origins[:, :2].mean(0)
    ref = origins[args.ref_setup]
    print(f"{len(files)} Standpunkte; Plot-Zentrum ({center[0]:.2f},{center[1]:.2f}), "
          f"Radius {args.plot_radius} m; Referenz-Ursprung Setup {args.ref_setup+1}")

    x, y, z = load_merged(files, center, args.plot_radius)
    print(f"Zusammengefuehrt: {len(x):,} Punkte")
    ground, gkey = ground_model(x, y, z)
    stems = detect_stems(x, y, z, ground, gkey)
    # nur Staemme im Plot-Radius werten
    stems = [s for s in stems if math.hypot(s["x"]-center[0], s["y"]-center[1]) <= args.plot_radius]
    if not stems:
        sys.exit("Keine Staemme im Plot gefunden.")

    # ---- Einzelbaumwerte ----
    ox, oy, oz = ref
    trees = []
    for i, s in enumerate(sorted(stems, key=lambda s: -s["r"]), 1):
        bhd = 2 * s["r"] * 100                      # cm
        ba = math.pi * s["r"]**2                    # m^2
        h = s["h"]
        valid_h = math.isfinite(h) and h > 3.0
        vol = ba * h * args.form_factor if valid_h else None
        slender = (h*100 / bhd) if (valid_h and bhd > 0) else None
        trees.append({
            "id": f"t{i:03d}",
            "world": [float(s["x"]-ox), float(s["g"]+1.3-oz), float(-(s["y"]-oy))],
            "e57": [round(float(s["x"]), 3), round(float(s["y"]), 3), round(float(s["g"]+1.3), 3)],
            "BHD_cm": round(bhd, 1),
            "Grundflaeche_m2": round(ba, 4),
            "Hoehe_m": round(h, 1) if valid_h else None,
            "Volumen_m3": round(vol, 3) if vol else None,
            "Schlankheit_hd": round(slender, 1) if slender else None,
            "Fit_RMS_cm": round(s["rms"], 1) if False else round(s["rms"]*100, 1),
            "Punkte": int(s["n"]),
        })

    # ---- Bestandeskennwerte ----
    area_ha = math.pi * args.plot_radius**2 / 10000.0
    bhds = np.array([t["BHD_cm"] for t in trees])
    bas = np.array([t["Grundflaeche_m2"] for t in trees])
    hs = np.array([t["Hoehe_m"] for t in trees if t["Hoehe_m"] is not None])
    vols = np.array([t["Volumen_m3"] for t in trees if t["Volumen_m3"] is not None])
    N = len(trees)
    G = float(bas.sum())
    Dg = float(math.sqrt((bhds**2).mean()))         # quadratisches Mittel
    n_top = max(1, round(100 * area_ha))            # entspr. 100 Baeume/ha
    h_top = float(np.sort(hs)[::-1][:n_top].mean()) if len(hs) else None
    sdi = float((N/area_ha) * (Dg/25.0)**1.605)
    hist_edges = list(range(0, int(bhds.max())+10, 10))
    hist = np.histogram(bhds, bins=hist_edges)[0].tolist()

    stand = {
        "plot_radius_m": args.plot_radius,
        "plot_area_ha": round(area_ha, 4),
        "n_standpunkte": len(files),
        "quantitativ": {
            "Stammzahl_N": N,
            "Stammzahl_N_ha": round(N / area_ha),
            "Grundflaeche_m2": round(G, 2),
            "Grundflaeche_m2_ha": round(G / area_ha, 1),
            "BHD_mittel_cm": round(float(bhds.mean()), 1),
            "Dg_cm": round(Dg, 1),
            "BHD_min_cm": round(float(bhds.min()), 1),
            "BHD_max_cm": round(float(bhds.max()), 1),
            "Hoehe_mittel_m": round(float(hs.mean()), 1) if len(hs) else None,
            "Oberhoehe_h100_m": round(h_top, 1) if h_top else None,
            "Vorrat_m3": round(float(vols.sum()), 1) if len(vols) else None,
            "Vorrat_m3_ha": round(float(vols.sum()) / area_ha, 1) if len(vols) else None,
            "Schlankheit_hd_mittel": round(float(np.mean([t["Schlankheit_hd"]
                                       for t in trees if t["Schlankheit_hd"]])), 1)
                                       if any(t["Schlankheit_hd"] for t in trees) else None,
            "SDI_Reineke": round(sdi),
        },
        "bhd_verteilung": {"kanten_cm": hist_edges, "anzahl": hist},
        "qualitativ": {
            "Baumart": "Picea abies (Fichte) - Standortdokumentation ICOS IT-Ren, "
                       "geometrisch nicht ableitbar",
            "Struktur": ("einschichtig/gleichaltrig" if bhds.std() < 10 else
                         "mehrschichtig/ungleichaltrig")
                        + f" (BHD-Streuung {bhds.std():.0f} cm)",
            "Vollstaendigkeit": f"{len(hs)}/{N} Baeume mit valider Hoehe; "
                                f"Erfassung nimmt zum Plot-Rand durch Verdeckung ab",
        },
        "methodik": "Geometrische Stammerkennung (Kasa-Kreis-Fit im 1,1-1,5-m-Band) "
                    "auf zusammengefuehrter 4-Scan-TLS; Volumen = Grundflaeche*Hoehe*"
                    f"{args.form_factor} (Formfaktor); SDI nach Reineke.",
    }

    out = {"ref_origin_e57": [float(v) for v in ref], "plot_center_xy": [float(center[0]), float(center[1])],
           "stand": stand, "trees": trees}
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    q = stand["quantitativ"]
    print(f"\n-> {args.out}")
    print(f"   {N} Staemme im Plot ({area_ha*10000:.0f} m^2 = {area_ha:.3f} ha)")
    print(f"   Stammzahl {q['Stammzahl_N_ha']}/ha | G {q['Grundflaeche_m2_ha']} m2/ha | "
          f"Dg {q['Dg_cm']} cm | Oberhoehe {q['Oberhoehe_h100_m']} m | "
          f"Vorrat {q['Vorrat_m3_ha']} m3/ha | SDI {q['SDI_Reineke']}")


if __name__ == "__main__":
    main()
