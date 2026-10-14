#!/usr/bin/env python3
"""paperC_laut.py -- BHD-Fehler gegen FELD-BHD in Abhaengigkeit der Abdeckung (LAUT, Paper C).

LAUT (Gollob et al. 2020, CC BY 4.0): 20 oesterreichische Inventurpunkte, TLS (Faro
Focus3D X330) und Feldreferenz je Baum (Position X/Y im Plotsystem, BHD in cm).
Eingabe: Brusthoehenbaender aus ext_band.py (extdata/laut/tls_plot_<n>_band.npz)
und reference_data.csv.

Je Baum: Punkte des Bandes 1,0-1,6 m im Umkreis BHD/2 + 25 cm um die Feldposition;
Kasa-Mittelpunkt; beobachteter Bogen (16 Sektoren wie 3DFin und 5-Grad-Klassen);
alle Verfahren; Fehler gegen den Feld-BHD. Zusaetzlich fuer Baeume mit >= 330 Grad
beobachtetem Bogen die kuenstliche Reduktion wie in paperC_real.py, ebenfalls
gegen den FELD-BHD.

Hinweis: Die Feldposition hat Messfehler; Baeume, deren Kasa-Mittelpunkt mehr als
30 cm von ihr abweicht, werden als 'Zuordnung unsicher' markiert, nicht verworfen.

  python scripts/paperC_laut.py extdata/laut --out Paper_ODT/Forst_Benchmark_Paper/results/real_laut.csv
"""
import argparse
import csv
import glob
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import dbh_methods as dm                                   # noqa: E402
from paperC_real import estimate, METHODS                  # noqa: E402

ARCS = [90, 135, 180, 202.5, 225, 270, 360]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lautdir"); ap.add_argument("--out", required=True)
    ap.add_argument("--min-dbh", type=float, default=7.0)
    ap.add_argument("--reps", type=int, default=5); ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--plots", help="nur diese Plot-Nummern, kommagetrennt")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    import pandas as pd
    ref = pd.read_csv(Path(a.lautdir) / "reference_data.csv")
    rows = []
    for f in sorted(glob.glob(str(Path(a.lautdir) / "tls_plot_*_band.npz"))):
        pid = int(re.search(r"tls_plot_(\d+)", f).group(1))
        if a.plots and pid not in {int(x) for x in a.plots.split(",")}:
            continue
        d = np.load(f)
        P = np.stack([d["x"], d["y"], d["hag"]], 1).astype(np.float64)
        P = P[(P[:, 2] >= 1.0) & (P[:, 2] <= 1.6)]
        trees = ref[(ref.plot_id == pid) & (ref.dbh >= a.min_dbh)]
        if not len(trees):
            continue
        # Plot-Koordinaten: Referenz relativ zum Plotzentrum; Wolke ggf. absolut ->
        # Versatz ueber den Median der Wolke schaetzen, wenn die Bereiche nicht passen
        off = np.zeros(2)
        if np.median(np.abs(P[:, :2])) > 200:
            off = np.median(P[:, :2], axis=0)
        from scipy.spatial import cKDTree
        tree = cKDTree(P[:, :2] - off)
        for _, t in trees.iterrows():
            r0 = t.dbh / 200
            idx = tree.query_ball_point([t.X, t.Y], r0 + .25)
            S = P[idx] - np.array([off[0], off[1], 0])
            base = {"plot": pid, "tree": int(t.tree_id), "species": t.tree_spec, "dbh_field_cm": t.dbh,
                    "cb_m": t.cb, "slope": t.slope, "n_pts": len(S)}
            if len(S) < 20:
                rows.append({**base, "kind": "observed", "arc_sec_deg": 0, "arc5_deg": 0, "center_off_m": ""}); continue
            fit = dm.fit_circle(S[:, 0], S[:, 1])
            if fit is None:
                rows.append({**base, "kind": "observed", "arc_sec_deg": 0, "arc5_deg": 0, "center_off_m": ""}); continue
            cx, cy = fit[0], fit[1]
            ang = np.degrees(np.arctan2(S[:, 1] - cy, S[:, 0] - cx))
            sec = np.count_nonzero(np.histogram(ang, bins=16, range=(-180, 180))[0]) * 22.5
            a5 = np.count_nonzero(np.histogram(ang, bins=72, range=(-180, 180))[0]) * 5
            est = estimate(S)
            row = {**base, "kind": "observed", "arc_sec_deg": sec, "arc5_deg": a5,
                   "center_off_m": round(float(np.hypot(cx - t.X, cy - t.Y)), 3)}
            row.update({f"{m}_cm": ("" if est[m] is None else est[m]) for m in METHODS})
            rows.append(row)
            if a5 >= 330:
                for th in ARCS:
                    for rep in range(a.reps):
                        mid = rng.uniform(-180, 180)
                        keep = np.abs((ang - mid + 180) % 360 - 180) <= th / 2
                        e = estimate(S[keep])
                        rr = {**base, "kind": "reduced", "arc_sec_deg": th, "arc5_deg": th, "center_off_m": row["center_off_m"], "rep": rep}
                        rr.update({f"{m}_cm": ("" if e[m] is None else e[m]) for m in METHODS})
                        rows.append(rr)
        print(f"Plot {pid}: {len(trees)} Baeume", flush=True)
    keys = sorted({k for r in rows for k in r}, key=lambda k: (k not in rows[0], k))
    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(rows)
    print(f"-> {out}: {len(rows)} Zeilen")


if __name__ == "__main__":
    main()
