#!/usr/bin/env python3
"""bench_dbh.py -- BHD-Genauigkeit mehrerer TLS-Methoden gegen Feld-Ground-Truth.

Vergleicht die BHD-Schaetzung verschiedener Verfahren auf denselben dichten
Einzelbaum-Wolken (SYSSIFOSS, data/dataverse_files/*.laz) gegen die unabhaengige
FELD-Inventur (pytreedb, Quelle "FI"). Kein geratener Wert -- jede Zahl ist ein
echter Lauf gegen gemessene Wahrheit.

Methoden:
  * baseline   numpy-Kreisfit an der Brusthoehen-Scheibe (LAUB-ON, ganze Wolke)
  * qsm_wood   derselbe Kreisfit, aber nur auf HOLZ-Punkten (Classification 0 =
               Holz, SYSSIFOSS-GT) -- das ist per Definition das QSM-BHD
               (2*Median-Stammradius bei 1,3 m; aRchi ist aus CRAN archiviert,
               der Holz-Stamm-Fit ist dessen BHD-Kern)
  * 3dfin      3DFin (Python, dendromatics) -- optional, wenn installiert
  * csp        CspStandSegmentation (R, Uni Freiburg) -- via scripts/bench_dbh_csp.R,
               Ergebnis-CSV wird hier eingelesen (siehe BENCH_DBH.md)

Feld-GT wird aus der oeffentlichen pytreedb geladen (geojsons.zip, Quelle "FI").
FORTLS ist bewusst NICHT dabei: es setzt Einzelscan-Radialgeometrie voraus und
laesst sich auf die kombinierten Mehr-Scan-Wolken nicht anwenden.

  python scripts/bench_dbh.py [--data data/dataverse_files] [--no-3dfin]

Voraussetzungen: siehe scripts/BENCH_DBH.md (R 4.4.x + Pakete, 3DFin via pip).
"""
import argparse
import glob
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from inventory_from_cloud import fit_circle          # noqa: E402

PYTREEDB_ZIP = ("https://raw.githubusercontent.com/3dgeo-heidelberg/pytreedb/"
                "main/data/geojson/geojsons.zip")


def field_gt():
    """Feld-BHD (Quelle 'FI') + Hoehe je Baum-ID aus der pytreedb."""
    raw = urllib.request.urlopen(PYTREEDB_ZIP, timeout=60).read()
    z = zipfile.ZipFile(io.BytesIO(raw))
    gt = {}
    for n in z.namelist():
        if not n.endswith(".geojson"):
            continue
        p = json.loads(z.read(n)).get("properties", {})
        ms = p.get("measurements", [])
        fi = [m for m in ms if isinstance(m, dict) and m.get("source") == "FI"]
        if fi and fi[0].get("DBH_cm") is not None:
            gt[Path(n).stem] = {"species": p.get("species"),
                                "DBH_cm": float(fi[0]["DBH_cm"])}
    return gt


def read_laz(path):
    import laspy
    las = laspy.read(path)
    xyz = np.c_[np.asarray(las.x), np.asarray(las.y), np.asarray(las.z)].astype(float)
    cls = np.asarray(las.classification)
    return xyz, cls


def bh_circle_dbh(xyz):
    """BHD aus Kreisfit an der Brusthoehen-Scheibe (lokal zentriert)."""
    xyz = xyz - xyz.min(0)
    g = np.percentile(xyz[:, 2], 1)
    sl = xyz[(xyz[:, 2] - g >= 1.2) & (xyz[:, 2] - g <= 1.4)]
    if len(sl) < 30:
        return None
    fit = fit_circle(sl[:, 0], sl[:, 1])
    if fit and fit[2] < 1.0:
        return round(2 * fit[2] * 100, 1)
    return None


def dbh_3dfin(las_path, outdir):
    """3DFin-BHD (Spalte 2, m, von <stem>_dbh_and_heights.txt). None bei Fehler."""
    from three_d_fin.processing.configuration import FinConfiguration
    from three_d_fin.processing.standalone_processing import StandaloneLASProcessing
    outdir.mkdir(parents=True, exist_ok=True)
    cfg = FinConfiguration()
    cp = getattr(cfg, "model_copy", None) or cfg.copy
    misc = (getattr(cfg.misc, "model_copy", None) or cfg.misc.copy)(update={
        "input_file": Path(las_path), "output_dir": outdir,
        "is_normalized": False, "is_noisy": True, "export_txt": True})
    try:
        StandaloneLASProcessing(cp(update={"misc": misc})).process()
    except Exception:
        return None
    dh = outdir / f"{Path(las_path).stem}_dbh_and_heights.txt"
    if not dh.exists():
        return None
    d = [float(r.split()[1]) for r in dh.read_text().splitlines()
         if len(r.split()) >= 2]
    return round(max(d) * 100, 1) if d else None


def write_local_las(xyz, path):
    import laspy
    loc = xyz - xyz.min(0)
    hdr = laspy.LasHeader(point_format=3); hdr.offsets = loc.min(0); hdr.scales = [0.001]*3
    o = laspy.LasData(hdr); o.x, o.y, o.z = loc[:, 0], loc[:, 1], loc[:, 2]
    o.write(str(path))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(REPO / "data" / "dataverse_files"))
    ap.add_argument("--no-3dfin", action="store_true")
    ap.add_argument("--csp-csv", default=None, help="Ergebnis von bench_dbh_csp.R")
    ap.add_argument("--out", default=str(REPO / "platform" / "web" / "gallery"
                                         / "bench_dbh_results.csv"))
    args = ap.parse_args()

    print("Feld-GT aus pytreedb laden ...")
    gt = field_gt()
    lasdir = Path(args.data)
    lasout = REPO / "data" / "_bench_las"; lasout.mkdir(parents=True, exist_ok=True)
    csp = {}
    if args.csp_csv and Path(args.csp_csv).exists():
        import csv as _c
        csp = {r["id"]: r["csp_DBH_cm"] for r in _c.DictReader(open(args.csp_csv))}

    rows = []
    for laz in sorted(glob.glob(str(lasdir / "*.laz"))):
        tid = "_".join(Path(laz).stem.split("_")[:3])   # Art_Plot_NN
        g = gt.get(tid)
        if not g:
            continue                                     # nur Baeume mit Feld-BHD
        xyz, cls = read_laz(laz)
        base = bh_circle_dbh(xyz)
        wood = bh_circle_dbh(xyz[cls == 0]) if (cls == 0).any() else None
        tdf = None
        if not args.no_3dfin:
            las_p = lasout / f"{tid}.las"; write_local_las(xyz, las_p)
            tdf = dbh_3dfin(las_p, lasout / tid)
        cv = csp.get(tid)
        row = {"id": tid, "species": g["species"], "field_DBH_cm": g["DBH_cm"],
               "baseline_DBH_cm": base, "qsm_wood_DBH_cm": wood,
               "3dfin_DBH_cm": tdf,
               "csp_DBH_cm": float(cv) if cv not in (None, "", "NA") else None}
        rows.append(row)
        print(f"{tid:20} Feld {g['DBH_cm']:5.1f} | base {base} wood {wood} "
              f"3dfin {tdf} csp {row['csp_DBH_cm']}")

    # Ergebnis + MAE (ohne Baeume <=15 cm, an denen alle Stammfits scheitern)
    import csv
    cols = ["id", "species", "field_DBH_cm", "baseline_DBH_cm", "qsm_wood_DBH_cm",
            "3dfin_DBH_cm", "csp_DBH_cm"]
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    print(f"\n-> {args.out}  ({len(rows)} Baeume mit Feld-BHD)")
    for m in ("baseline", "qsm_wood", "3dfin", "csp"):
        e = [abs(r[f"{m}_DBH_cm"] - r["field_DBH_cm"]) for r in rows
             if r.get(f"{m}_DBH_cm") is not None and r["field_DBH_cm"] > 15]
        if e:
            print(f"  {m:9} MAE (>15 cm): {np.mean(e):.1f} cm (n={len(e)})")


if __name__ == "__main__":
    main()
