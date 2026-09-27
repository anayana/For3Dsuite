#!/usr/bin/env python3
"""bench_qsm_wytham.py -- eigenes QSM gegen die TreeQSM-Referenz halten.

Das QSM dieser Suite (scripts/qsm_cloud.py) entstand in Python, weil aRchi aus
CRAN archiviert ist und die R-Umgebung nicht lief. Es hat deshalb NIE einen
Referenzvergleich gesehen -- Holzvolumen und Verzweigungsordnung waren die
letzten voellig ungeprueften Zahlen der Suite.

Wytham Woods (Calders et al., Zenodo 10.5281/zenodo.7307956, CC-BY-4.0) schliesst
die Luecke: 876 Einzelbaum-Punktwolken MIT den zugehoerigen, optimierten
TreeQSM-v2.0-Modellen. Aufgenommen laubfrei (RIEGL VZ-400, Winter) -- damit
entfaellt die Blattfilterung als Stoerfaktor und verglichen wird wirklich die
Modellierung.

Fairer Massstab: die Referenztabelle liefert zu jedem Wert auch die STREUUNG der
TreeQSM-Laeufe selbst (Vol_QSM_sd, DBH_QSM_sd). Eine Abweichung ist erst dann
gross, wenn sie ueber die Eigenstreuung des Referenzverfahrens hinausgeht -- sonst
misst man Rauschen.

  python scripts/bench_qsm_wytham.py --plydir data/wytham/ply \\
      --ref data/wytham/tls_summary.csv --out data/wytham/bench_qsm.csv
"""
import argparse
import csv
import json
import math
import re
import statistics as st
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]


def read_ply(path):
    """Minimaler PLY-Leser (ascii und binary_little_endian), nur x/y/z."""
    with open(path, "rb") as f:
        if f.readline().strip() != b"ply":
            raise ValueError("kein PLY")
        fmt, n, props = None, 0, []
        while True:
            ln = f.readline().decode("ascii", "replace").strip()
            if ln.startswith("format"):
                fmt = ln.split()[1]
            elif ln.startswith("element vertex"):
                n = int(ln.split()[2])
            elif ln.startswith("property") and not ln.startswith("property list"):
                props.append(ln.split()[1:])
            elif ln == "end_header":
                break
        names = [p[1] for p in props]
        if fmt == "ascii":
            arr = np.loadtxt(f, max_rows=n)
            cols = {nm: arr[:, i] for i, nm in enumerate(names)}
        else:
            NP = {"float": "f4", "float32": "f4", "double": "f8", "float64": "f8",
                  "uchar": "u1", "uint8": "u1", "char": "i1", "int8": "i1",
                  "ushort": "u2", "uint16": "u2", "short": "i2", "int16": "i2",
                  "uint": "u4", "uint32": "u4", "int": "i4", "int32": "i4"}
            dt = np.dtype([(p[1], "<" + NP[p[0]]) for p in props])
            data = np.frombuffer(f.read(dt.itemsize * n), dtype=dt, count=n)
            cols = {nm: data[nm].astype(np.float64) for nm in names}
    return np.c_[cols["x"], cols["y"], cols["z"]]


def run_qsm(xyz, workdir, label, seg_len, voxel):
    """qsm_cloud.py auf einen EINZELNEN, bereits segmentierten Baum anwenden.

    Die Suite modelliert sonst plotweise: sie braucht ITCD-Label und eine
    Stammliste. Beides ist hier trivial -- der Baum ist schon isoliert, also
    bekommt jeder Punkt dasselbe Label und die Stammposition faellt aus der
    Brusthoehen-Scheibe.
    """
    shift = np.floor(xyz.min(axis=0))
    np.savez(workdir / "cloud.npz", xyz=(xyz - shift).astype(np.float32),
             rgb=np.full((len(xyz), 3), 160, np.uint8), shift=shift)
    np.savez_compressed(workdir / "itcd.npz",
                        label=np.zeros(len(xyz), np.int32),
                        labels_txt=np.array([label], dtype=object),
                        stems=np.zeros((1, 2)), voxel=np.float64(voxel))
    g = np.percentile(xyz[:, 2], 1)
    h = xyz[:, 2] - g
    sl = xyz[(h >= 1.1) & (h <= 1.5)]
    if len(sl) < 20:
        sl = xyz[h <= 2.0]
    cx, cy = float(sl[:, 0].mean()), float(sl[:, 1].mean())
    with open(workdir / "stems.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["label", "x", "y", "z", "BHD_cm"])
        w.writerow([label, round(cx, 3), round(cy, 3), round(g + 1.3, 3), ""])

    cmd = [sys.executable, str(REPO / "scripts" / "qsm_cloud.py"),
           str(workdir / "cloud.npz"), str(workdir / "itcd.npz"),
           "--stems", str(workdir / "stems.csv"),
           "--out", str(workdir / "qsm"),
           "--origin", "0", "0", "0", "--radius", "999",
           "--seg-len", str(seg_len), "--voxel", str(voxel)]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    js = workdir / "qsm.json"
    if p.returncode != 0 or not js.exists():
        return None, (p.stderr or p.stdout).strip().splitlines()[-1:] or ["?"]
    d = json.loads(js.read_text(encoding="utf-8"))
    trees = d.get("baeume") or {}
    return (trees.get(label) or next(iter(trees.values()), None)), None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plydir", default="data/wytham/ply")
    ap.add_argument("--ref", default="data/wytham/tls_summary.csv")
    ap.add_argument("--out", default="data/wytham/bench_qsm.csv")
    ap.add_argument("--seg-len", type=float, default=0.4)
    ap.add_argument("--voxel", type=float, default=0.02)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    ref = {r["Tree_ID"]: r for r in csv.DictReader(open(args.ref, encoding="utf-8-sig"))}
    plys = sorted(Path(args.plydir).glob("*.ply"))
    if args.limit:
        plys = plys[:args.limit]
    print(f"{len(plys)} Baeume, Referenz aus {Path(args.ref).name}\n")

    rows = []
    for p in plys:
        tid = re.sub(r"^wytham_winter_", "", p.stem)
        r = ref.get(tid)
        if not r:
            print(f"  {tid}: keine Referenz -- uebersprungen")
            continue
        xyz = read_ply(p)
        with tempfile.TemporaryDirectory() as td:
            res, err = run_qsm(xyz, Path(td), f"Baum {tid}", args.seg_len, args.voxel)
        f = lambda k: float(r[k]) if r.get(k) not in (None, "", "NA") else None  # noqa: E731
        row = {"tree_id": tid, "punkte": len(xyz),
               "ref_dbh_cm": (f("DBH_QSM_avg_[m]") or 0) * 100,
               "ref_dbh_sd_cm": (f("DBH_QSM_sd[m]") or 0) * 100,
               "ref_vol_l": (f("Vol_QSM_avg_[m3]") or 0) * 1000,
               "ref_vol_sd_l": (f("Vol_QSM_sd_[m3]") or 0) * 1000,
               "ref_hoehe_m": f("Hgt_pts_[m]")}
        if res is None:
            row["status"] = "fehler"
            row["fehler"] = (err or [""])[0][:90]
            print(f"  {tid:8} FEHLER: {row['fehler']}")
        else:
            row.update({"status": "ok",
                        "qsm_dbh_cm": res.get("bhd_qsm_cm"),
                        "qsm_vol_l": res.get("holzvolumen_l"),
                        "qsm_stammvol_l": res.get("stammvolumen_l"),
                        "qsm_zylinder": res.get("zylinder"),
                        "qsm_ordnung": res.get("max_ordnung")})
            dv = (row["qsm_vol_l"] - row["ref_vol_l"]) if row["qsm_vol_l"] else None
            print(f"  {tid:8} {len(xyz):7,} Pkt | BHD {row['ref_dbh_cm']:5.1f} ref / "
                  f"{(row['qsm_dbh_cm'] or 0):5.1f} eigen | Volumen "
                  f"{row['ref_vol_l']:8.1f} ± {row['ref_vol_sd_l']:5.1f} ref / "
                  f"{(row['qsm_vol_l'] or 0):8.1f} eigen"
                  + (f"  ({dv:+.0f} l)" if dv is not None else ""))
        rows.append(row)

    fields = ["tree_id", "status", "punkte", "ref_hoehe_m", "ref_dbh_cm",
              "ref_dbh_sd_cm", "qsm_dbh_cm", "ref_vol_l", "ref_vol_sd_l",
              "qsm_vol_l", "qsm_stammvol_l", "qsm_zylinder", "qsm_ordnung", "fehler"]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    print(f"\n-> {args.out}")

    ok = [r for r in rows if r["status"] == "ok" and r.get("qsm_vol_l")]
    if not ok:
        return
    dv = [r["qsm_vol_l"] - r["ref_vol_l"] for r in ok]
    rel = [100 * (r["qsm_vol_l"] - r["ref_vol_l"]) / r["ref_vol_l"]
           for r in ok if r["ref_vol_l"] > 0]
    dd = [r["qsm_dbh_cm"] - r["ref_dbh_cm"] for r in ok if r.get("qsm_dbh_cm")]
    sd = [r["ref_vol_sd_l"] for r in ok]
    print(f"\n{len(ok)} Baeume ausgewertet")
    print(f"  Holzvolumen  Bias {st.mean(dv):+8.1f} l   "
          f"Median {st.median(dv):+8.1f} l   "
          f"mittlerer Betrag {st.mean(map(abs, dv)):7.1f} l")
    if rel:
        print(f"               relativ Median {st.median(rel):+6.1f} %")
    print(f"  Eigenstreuung von TreeQSM selbst: im Mittel ± {st.mean(sd):.1f} l "
          f"-- Abweichungen darunter sind Rauschen, keine Aussage")
    if dd:
        print(f"  QSM-BHD      Bias {st.mean(dd):+6.2f} cm   "
              f"mittlerer Betrag {st.mean(map(abs, dd)):5.2f} cm")


if __name__ == "__main__":
    main()
