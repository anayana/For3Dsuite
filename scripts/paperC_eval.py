#!/usr/bin/env python3
"""paperC_eval.py -- Scan-Konfigurationen aus dem Standpunkt-Pool auswerten (Paper C).

Liest eine Szene von paperC_scene.py (truth.csv, pool.csv) und die gepackten
Standpunkte (paperC_pack.py: legs/legNNN.npz). Setzt Konfigurationen als
Teilmengen des Pools zusammen und misst je Stamm im Kernplot:

  arc_geo_deg  geometrisch sichtbarer Umfang (Grad) aus allen Standpunkten der Konfiguration
  arc_deg      belegte Sektoren (16 x 22,5 Grad) um das WAHRE Zentrum, Brusthoehe +/-5 cm (wie 3DFin)
  arc1_deg     belegte 1-Grad-Klassen (unterschaetzt bei duennen Punkten)
  n_bh         Punkte in der 10-cm-Scheibe
  BHD je Verfahren (kreisfit, geofit, ransac, zylinder, hough, robust) auf dem
               Band 1,05-1,55 m, Fehler gegen den wahren BHD (Ellipsenumfang/pi)

Stammpunkte werden ueber die HELIOS-Objekt-ID zugeordnet (perfekte Segmentierung).
Damit misst die Auswertung Abdeckung und Durchmesserschaetzung getrennt von der
Detektion; Detektion wird gesondert mit 3DFin geprueft.

Konfigurationen: n = 1, 2, 3, 4, 6, 9 Standpunkte x
  raster   gleichmaessig verteilte Rasterpunkte (Greedy-Maximin ab Plotmitte)
  zufall   10 Zufallsziehungen aus dem ganzen Pool
  eng      die n Pool-Punkte naechst der Plotmitte (wie Renon: wenige Standpunkte eng)

  python scripts/paperC_eval.py data/paperC/S1b --out Paper_ODT/Forst_Benchmark_Paper/results/helios_S1b.csv
"""
import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import dbh_methods as dm                                   # noqa: E402
from arc_error_mc_real import m_hough, m_robust            # noqa: E402

NS = [1, 2, 3, 4, 6, 9]
N_RANDOM = 10


def visibility(truth, pool, nang=360, cos_min=0.1):
    """Geometrisch sichtbarer Anteil jedes Kernstamms je Standpunkt in Brusthoehe:
    360 Punkte auf dem wahren elliptischen Umfang; sichtbar, wenn dem Scanner
    zugewandt (Einfall cos > cos_min, wie im Scanplaner) und die Sichtlinie keinen
    anderen Stamm schneidet. Ergebnis {leg: bool[n_kern, nang]} -- unabhaengig von
    der Punktdichte, daher die Wahrheit fuer 'wie viel Umfang war sichtbar'."""
    st = truth[truth.kind.isin(["stem", "under"])]
    core = truth[(truth.kind == "stem") & (truth.core == 1)]
    th = np.linspace(0, 2 * np.pi, nang, endpoint=False)
    # Umfangspunkte und Normalen der Kernstaemme (Ellipse a, b, Drehung rot)
    P, N = [], []
    for _, t in core.iterrows():
        ang = th - t.rot_rad
        rad = t.a_m * t.b_m / np.sqrt((t.b_m * np.cos(ang)) ** 2 + (t.a_m * np.sin(ang)) ** 2)
        px, py = t.x + rad * np.cos(th), t.y + rad * np.sin(th)
        # Normale der Ellipse numerisch aus Nachbarpunkten
        tx, ty = np.roll(px, -1) - np.roll(px, 1), np.roll(py, -1) - np.roll(py, 1)
        nx, ny = ty, -tx
        s = np.sign(nx * (px - t.x) + ny * (py - t.y)); nl = np.hypot(nx, ny)
        P.append(np.stack([px, py], 1)); N.append(np.stack([nx * s / nl, ny * s / nl], 1))
    P, N = np.array(P), np.array(N)                                   # (S, A, 2)
    occ = st[["x", "y"]].values; occ_r = np.maximum(st.a_m.values, st.b_m.values)
    own = {sid: j for j, sid in enumerate(st.id.values)}
    out = {}
    for _, lg in pool.iterrows():
        sp = np.array([lg.x, lg.y])
        v = sp[None, None, :] - P                                     # Punkt -> Scanner
        d = np.linalg.norm(v, axis=2)
        cosi = np.einsum("sak,sak->sa", N, v) / d
        vis = cosi > cos_min
        # Verdeckung: Abstand der Strecke Scanner-Punkt zu jedem anderen Stammzentrum
        u = v / d[..., None]
        for j, cid in enumerate(core.id.values):
            cand = np.flatnonzero(np.hypot(*(occ - sp).T) < d[j].max() + 1.5)
            cand = cand[cand != own[cid]]
            if not len(cand):
                continue
            w = occ[cand][None, :, :] - P[j][:, None, :]               # (A, C, 2)
            proj = np.einsum("ack,ak->ac", w, u[j])
            perp = np.abs(w[..., 0] * u[j][:, None, 1] - w[..., 1] * u[j][:, None, 0])
            hit = (proj > 0) & (proj < d[j][:, None]) & (perp < occ_r[cand][None, :])
            vis[j] &= ~hit.any(axis=1)
        out[int(lg.leg)] = vis
    return core.id.values, out


def configs(pool, L, seed):
    rng = np.random.default_rng(seed)
    grid = pool[pool.kind == "grid"]
    c = np.array([L / 2, L / 2])
    out = []
    for n in NS:
        # raster: Greedy-Maximin ueber die Rasterpunkte, Start am mittelnaechsten
        g = grid[["x", "y"]].values
        sel = [int(np.argmin(np.hypot(*(g - c).T)))]
        while len(sel) < n:
            d = np.min(np.hypot(g[:, None, 0] - g[None, sel, 0], g[:, None, 1] - g[None, sel, 1]), axis=1)
            sel.append(int(np.argmax(d)))
        out.append(("raster", n, 0, list(grid.leg.values[sel])))
        for k in range(N_RANDOM):
            out.append(("zufall", n, k, list(rng.choice(pool.leg.values, n, replace=False))))
        d = np.hypot(pool.x - c[0], pool.y - c[1])
        out.append(("eng", n, 0, list(pool.leg.values[np.argsort(d.values)[:n]])))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--out", required=True)
    ap.add_argument("--L", type=float, default=40)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--methods", default="kreisfit,geofit,ransac,zylinder,hough,robust")
    args = ap.parse_args()
    sc = Path(args.scene)
    truth = pd.read_csv(sc / "truth.csv")
    stems = truth[(truth.kind == "stem") & (truth.core == 1)].set_index("id")
    pool = pd.read_csv(sc / "pool.csv")
    legs = {}
    for f in sorted((sc / "legs").glob("leg*.npz")):
        z = np.load(f)
        m = np.isin(z["obj"], stems.index.values)
        legs[int(f.stem[3:])] = {k: z[k][m] for k in ("x", "y", "z", "obj")}
    pool = pool[pool.leg.isin(legs)]
    methods = args.methods.split(",")
    core_ids, vis = visibility(truth, pool)
    vrow = {sid: k for k, sid in enumerate(core_ids)}
    rows = []
    cfgs = configs(pool, args.L, args.seed)
    for i, (lay, n, rep, sel) in enumerate(cfgs, 1):
        if len(sel) < n:
            continue
        P = {k: np.concatenate([legs[l][k] for l in sel]) for k in ("x", "y", "z", "obj")}
        order = np.argsort(P["obj"], kind="stable")
        obj = P["obj"][order]; X = P["x"][order]; Y = P["y"][order]; Z = P["z"][order]
        bounds = np.searchsorted(obj, stems.index.values, side="left"), np.searchsorted(obj, stems.index.values, side="right")
        sx, sy = pool.set_index("leg").loc[sel, "x"].values, pool.set_index("leg").loc[sel, "y"].values
        for (sid, t), a, b in zip(stems.iterrows(), *bounds):
            x, y, z = X[a:b], Y[a:b], Z[a:b]
            bh = np.abs(z - 1.3) <= .05
            ang = np.degrees(np.arctan2(y[bh] - t.y, x[bh] - t.x))
            sec = int(np.count_nonzero(np.histogram(ang, bins=16, range=(-180, 180))[0]))
            fine = int(np.count_nonzero(np.histogram(ang, bins=360, range=(-180, 180))[0]))
            row = {"layout": lay, "n_scans": n, "rep": rep, "stem": sid, "dbh_true_cm": t.dbh_true_cm,
                   "dist_min_m": round(float(np.min(np.hypot(sx - t.x, sy - t.y))), 2),
                   "n_bh": int(bh.sum()), "arc_deg": sec * 22.5, "arc1_deg": fine,
                   "arc_geo_deg": int(np.any([vis[l][vrow[sid]] for l in sel], axis=0).sum())}
            band = np.abs(z - 1.3) <= .25
            pts = np.stack([x, y, z], axis=1)
            sl = pts[band]
            est = {}
            if len(sl) >= 12:
                if "kreisfit" in methods: est["kreisfit"] = dm.m_kreisfit(sl)[0]
                if "geofit" in methods: est["geofit"] = dm.m_geofit(sl)
                if "ransac" in methods: est["ransac"] = dm.m_ransac(sl)[0]
                if "zylinder" in methods: est["zylinder"] = dm.m_zylinder(pts[(z >= 1.0) & (z <= 1.6)])[0]
                if "hough" in methods: est["hough"] = m_hough(sl)
                if "robust" in methods: est["robust"] = m_robust(sl)
            for m in methods:
                v = est.get(m)
                row[f"{m}_cm"] = "" if v is None else v
            rows.append(row)
        if i % 10 == 0:
            print(f"{i}/{len(cfgs)} Konfigurationen", flush=True)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {len(rows)} Stamm-Konfigurationen")


if __name__ == "__main__":
    main()
