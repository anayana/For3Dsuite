#!/usr/bin/env python3
"""paperC_bootstrap.py -- Konfidenzintervalle fuer Anteile und Schwellenboegen (Paper C).

Cluster-Bootstrap ueber STAEMME (nicht ueber Faelle): je Datensatz werden Staemme mit
Zuruecklegen gezogen, alle Faelle eines gezogenen Stamms gehen mit. Je Verfahren und
Bogenklasse: Anteil |Fehler| <= 2 cm (Ausfall = daneben) mit 95-%-Intervall, und der
Schwellenbogen 'kleinster Bogen, ab dem der Anteil >= 80 % fuer alle groesseren Boegen'
mit 95-%-Intervall.

  python scripts/paperC_bootstrap.py --out Paper_ODT/Forst_Benchmark_Paper/results/bootstrap.csv
"""
import argparse
import glob
from pathlib import Path

import numpy as np
import pandas as pd

RES = Path(__file__).resolve().parents[1] / "Paper_ODT" / "Forst_Benchmark_Paper" / "results"
M = ["kreisfit", "geofit", "ransac", "zylinder", "hough", "robust"]


def load():
    sets = {}
    h = []
    for sc in ("S1a", "S1b", "S1c"):
        f = RES / f"helios_{sc}.csv"
        if f.exists():
            x = pd.read_csv(f); x["sid"] = sc + "_" + x.stem.astype(str); h.append(x)
    if h:
        x = pd.concat(h); x["ref"] = x.dbh_true_cm
        x["arc"] = pd.cut(x.arc_geo_deg, [1, 90, 135, 180, 225, 270, 315, 361], right=False, labels=[45, 112.5, 157.5, 202.5, 247.5, 292.5, 338]).astype(float)
        sets["helios"] = x.dropna(subset=["arc"])
    f = RES / "helios_S1b_ast.csv"                         # S1b mit Aesten in Brusthoehe
    if f.exists():
        x = pd.read_csv(f); x["sid"] = "S1bB_" + x.stem.astype(str); x["ref"] = x.dbh_true_cm
        x["arc"] = pd.cut(x.arc_geo_deg, [1, 90, 135, 180, 225, 270, 315, 361], right=False, labels=[45, 112.5, 157.5, 202.5, 247.5, 292.5, 338]).astype(float)
        sets["helios_branches"] = x.dropna(subset=["arc"])
    for key in ("real_clean", "real"):
        fs = glob.glob(str(RES / key / "*.csv"))
        if fs:
            x = pd.concat([pd.read_csv(f).assign(p=Path(f).stem) for f in fs])
            x["sid"] = x.p + "_" + x.stem.astype(str); x["ref"] = x.ref_dbh_cm; x["arc"] = x.arc_deg
            sets["segforests_" + ("clean" if key == "real_clean" else "clutter")] = x
    fs = glob.glob(str(RES / "laut" / "*.csv"))
    if fs:
        x = pd.concat([pd.read_csv(f) for f in fs]); x = x[x.kind == "reduced"].copy()
        x["sid"] = x["plot"].astype(str) + "_" + x.tree.astype(str); x["ref"] = x.dbh_field_cm; x["arc"] = x.arc5_deg
        sets["laut"] = x
    return sets


def shares(x):
    out = {}
    for m in M:
        if m + "_cm" not in x:
            continue
        ok = ((x[m + "_cm"] - x.ref).abs() <= 2)
        out[m] = ok.groupby(x.arc).mean()
    return out


def threshold(s, level=.8):
    arcs = sorted(s.index); thr = np.nan
    for a in reversed(arcs):
        if s[a] >= level:
            thr = a
        else:
            break
    return thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RES / "bootstrap.csv"))
    ap.add_argument("--B", type=int, default=500)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    rows = []
    for name, x in load().items():
        x = x.copy(); x["sid"] = x.sid.astype(str)
        groups = {k: v.index.values for k, v in x.reset_index(drop=True).groupby("sid")}
        x = x.reset_index(drop=True); keys = np.array(list(groups))
        base = shares(x)
        boot = {m: [] for m in base}; bthr = {m: [] for m in base}
        for _ in range(a.B):
            pick = rng.choice(keys, len(keys), replace=True)
            xb = x.loc[np.concatenate([groups[k] for k in pick])]
            sb = shares(xb)
            for m in base:
                boot[m].append(sb[m].reindex(base[m].index)); bthr[m].append(threshold(sb[m]))
        for m in base:
            B = pd.concat(boot[m], axis=1)
            t = np.array(bthr[m], float)
            for arc, v in base[m].items():
                lo, hi = np.nanpercentile(B.loc[arc].values, [2.5, 97.5])
                rows.append({"dataset": name, "method": m, "arc": arc, "share2cm": round(v, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
                             "thr80": threshold(base[m]), "thr80_lo": np.nanpercentile(t, 2.5) if np.isfinite(t).any() else np.nan,
                             "thr80_hi": np.nanpercentile(t, 97.5) if np.isfinite(t).any() else np.nan,
                             "thr80_never": round(float(np.mean(~np.isfinite(t))), 3), "n_stems": len(keys)})
        print(name, "fertig", flush=True)
    pd.DataFrame(rows).to_csv(a.out, index=False)
    print("->", a.out)


if __name__ == "__main__":
    main()
