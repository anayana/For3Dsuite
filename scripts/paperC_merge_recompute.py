#!/usr/bin/env python3
"""paperC_merge_recompute.py -- neu gerechnete Verfahrensspalten in die Ergebnistabellen uebernehmen.

Die Teilneuberechnungen (--methods, gleiche Seeds) liefern dieselben Zeilen in derselben
Reihenfolge; uebernommen wird nur, wenn die Schluesselspalten Zeile fuer Zeile
uebereinstimmen. Quellen: results/recompute/ (Workflow compute-hough) und optional
weitere Dateien per --helios (lokale HELIOS-Laeufe).

  python scripts/paperC_merge_recompute.py --method hough --helios S1a=/pfad/helios_S1a.csv ...
"""
import argparse
import re
from pathlib import Path

import pandas as pd

RES = Path(__file__).resolve().parents[1] / "Paper_ODT" / "Forst_Benchmark_Paper" / "results"


def swap(target, new, keys, col):
    a = pd.read_csv(target); b = pd.read_csv(new)
    if len(a) != len(b) or not a[keys].fillna(-9).astype(str).equals(b[keys].fillna(-9).astype(str)):
        raise SystemExit(f"Schluessel passen nicht: {target.name} <- {new.name}")
    a[col] = b[col].values
    a.to_csv(target, index=False)
    return len(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="hough")
    ap.add_argument("--helios", nargs="*", default=[], help="Szene=Datei")
    a = ap.parse_args()
    col = f"{a.method}_cm"
    rc = RES / "recompute"
    n = 0
    for f in sorted(rc.glob("sf_*.csv")):
        mode, plot = re.match(r"sf_(clean|clutter)_(\d+)", f.stem).groups()
        tgt = RES / ("real_clean" if mode == "clean" else "real") / f"plot_{plot}.csv"
        b = pd.read_csv(f)
        if all(f"{m}_cm" in b for m in ("kreisfit", "geofit", "ransac", "zylinder", "hough", "robust")):
            b.to_csv(tgt, index=False); n += len(b)              # vollstaendige Neuberechnung
        else:
            n += swap(tgt, f, ["stem", "arc_deg", "rep", "n_pts"], col)
    for f in sorted(rc.glob("laut_*.csv")):
        plot = f.stem.split("_")[1]
        n += swap(RES / "laut" / f"plot_{plot}.csv", f, ["plot", "tree", "kind", "arc5_deg", "rep", "n_pts"], col)
    mcs = sorted(rc.glob("mc_*.csv"))
    if mcs:
        t = RES / "arc_error_mc_real.csv"; d = pd.read_csv(t)
        key = ["scenario", "method", "arc_deg", "n_pts", "dbh_cm"]
        new = pd.concat([pd.read_csv(f) for f in mcs])
        idx = d.set_index(key).index
        nidx = new.set_index(key).index
        if not nidx.isin(idx).all():
            raise SystemExit("MC: neue Zellen fehlen in der Tabelle")
        d = d.set_index(key); new = new.set_index(key)
        d.loc[new.index, new.columns] = new
        d.reset_index()[pd.read_csv(t, nrows=0).columns].to_csv(t, index=False); n += len(new)
    for spec in a.helios:
        sc, f = spec.split("=", 1)
        n += swap(RES / f"helios_{sc}.csv", Path(f), ["layout", "n_scans", "rep", "stem", "n_bh"], col)
    print(f"{col}: {n} Zeilen uebernommen")


if __name__ == "__main__":
    main()
