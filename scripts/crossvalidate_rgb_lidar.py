#!/usr/bin/env python3
"""crossvalidate_rgb_lidar.py -- Baustein 4, Validierungshebel: RGB <-> LiDAR/QSM.

Qualitativ (RGB, aus qualitative_rgb.py) und quantitativ (Struktur aus
LiDAR/QSM) am selben, georeferenzierten Baum kreuzvalidieren:

  * Uebereinstimmung  -> starkes Signal (Befund belastbar)
  * Widerspruch       -> mutmasslicher Fehler/Halluzination im RGB-Zweig, oder
                         Verdeckung/Belichtung im Bild -> markiert zur Pruefung

Vergleicht je Baum einen RGB-Vitalproxy (Default: Vital_gruen, hoeher = vitaler)
mit einer strukturellen Vitalitaetsgroesse (z. B. QSM-Astdichte, Kronen-
Punktdichte, Feinreisig-Anteil; hoeher = vitaler). Beide werden robust
z-standardisiert (Median/MAD), dann:

  RGB niedrig & Struktur niedrig -> "Schaden bestaetigt"
  RGB hoch    & Struktur hoch    -> "vital bestaetigt"
  RGB niedrig & Struktur hoch    -> "WIDERSPRUCH: RGB-Stress ohne Strukturverlust"
  RGB hoch    & Struktur niedrig -> "WIDERSPRUCH: Struktur licht, RGB gruen"
  sonst                          -> "unauffaellig"

Zusaetzlich Spearman-Rangkorrelation ueber alle gepaarten Baeume.

Strukturquelle wahlweise aus einer scene.json (Marker-Attribut) oder einer CSV.
Ideal-Eingang laut Baustein: QSM-Astdichte / obere-Kronen-Punktdichte aus
lidR/TreeLS; als Platzhalter dienen vorhandene Attribute (Punkte, Hoehe_m).

Nutzung:
  # RGB-CSV (qualitative_rgb.py) gegen ein Struktur-Attribut der scene.json
  python crossvalidate_rgb_lidar.py --rgb vital.csv \
      --scene scene.json --struct-attr Punkte --out xval.csv

  # ... oder gegen eine externe Struktur-CSV (z. B. QSM-Export)
  python crossvalidate_rgb_lidar.py --rgb vital.csv \
      --struct qsm.csv --struct-key label --struct-col Astdichte --out xval.csv
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_structural(args):
    """{key: wert} der strukturellen Groesse aus scene.json oder CSV."""
    if args.scene:
        scene = json.loads(Path(args.scene).read_text(encoding="utf-8"))
        out = {}
        for mk in scene.get("markers", []):
            v = as_float((mk.get("attributes") or {}).get(args.struct_attr))
            if v is not None:
                out[mk["id"]] = v
        if not out:
            sys.exit(f"Kein Marker mit Attribut '{args.struct_attr}' in {args.scene}")
        return out, args.struct_attr
    rows = read_csv(args.struct)
    out = {}
    for r in rows:
        v = as_float(r.get(args.struct_col))
        if v is not None and r.get(args.struct_key):
            out[r[args.struct_key]] = v
    if not out:
        sys.exit(f"Keine Werte aus {args.struct} (Spalten {args.struct_key}/{args.struct_col})")
    return out, args.struct_col


def robust_z(values):
    a = np.array(values, float)
    med = np.median(a)
    mad = np.median(np.abs(a - med)) or 1e-6
    return (a - med) / (1.4826 * mad)


def spearman(x, y):
    def ranks(a):
        order = np.argsort(a, kind="mergesort")
        r = np.empty(len(a), float)
        r[order] = np.arange(len(a), dtype=float)
        # Bindungen mitteln
        a = np.asarray(a)
        _, inv, cnt = np.unique(a, return_inverse=True, return_counts=True)
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, r)
        return (sums / cnt)[inv]
    rx, ry = ranks(x), ranks(y)
    rx, ry = rx - rx.mean(), ry - ry.mean()
    denom = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return float((rx * ry).sum() / denom) if denom else float("nan")


def classify(zr, zs, thr):
    lo_r, lo_s = zr <= -thr, zs <= -thr
    hi_r, hi_s = zr >= thr, zs >= thr
    if lo_r and lo_s:
        return "Schaden bestaetigt", True
    if hi_r and hi_s:
        return "vital bestaetigt", True
    if lo_r and hi_s:
        return "WIDERSPRUCH: RGB-Stress ohne Strukturverlust", False
    if hi_r and lo_s:
        return "WIDERSPRUCH: Struktur licht, RGB gruen", False
    return "unauffaellig", None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--rgb", required=True, help="CSV aus qualitative_rgb.py")
    ap.add_argument("--rgb-key", default="marker_id")
    ap.add_argument("--rgb-col", default="Vital_gruen",
                    help="RGB-Vitalproxy, hoeher = vitaler (Default Vital_gruen)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--scene", help="scene.json als Strukturquelle")
    src.add_argument("--struct", help="externe Struktur-CSV (z. B. QSM)")
    ap.add_argument("--struct-attr", default="Punkte",
                    help="Marker-Attribut in scene.json (Default Punkte)")
    ap.add_argument("--struct-key", default="label", help="Join-Spalte der Struktur-CSV")
    ap.add_argument("--struct-col", default="Astdichte", help="Wertspalte der Struktur-CSV")
    ap.add_argument("--struct-invert", action="store_true",
                    help="hohe Strukturwerte = weniger vital (z. B. Kronentransparenz)")
    ap.add_argument("--thr", type=float, default=1.0, help="z-Schwelle fuer 'niedrig/hoch'")
    ap.add_argument("--out", help="Ergebnis-CSV")
    args = ap.parse_args()

    rgb_rows = read_csv(args.rgb)
    rgb = {r[args.rgb_key]: as_float(r.get(args.rgb_col)) for r in rgb_rows
           if as_float(r.get(args.rgb_col)) is not None}
    struct, sname = load_structural(args)

    keys = [k for k in rgb if k in struct]
    if len(keys) < 3:
        sys.exit(f"Zu wenige gepaarte Baeume ({len(keys)}) fuer eine Kreuzvalidierung")

    rv = np.array([rgb[k] for k in keys])
    sv = np.array([struct[k] for k in keys])
    if args.struct_invert:
        sv = -sv
    zr, zs = robust_z(rv), robust_z(sv)
    rho = spearman(rv, sv)

    out_rows, agree, contra = [], 0, 0
    for i, k in enumerate(keys):
        verdict, ok = classify(zr[i], zs[i], args.thr)
        if ok is True:
            agree += 1
        elif ok is False:
            contra += 1
        out_rows.append({
            "key": k,
            "RGB": round(float(rv[i]), 4), "RGB_z": round(float(zr[i]), 2),
            sname: round(float(sv[i] if not args.struct_invert else -sv[i]), 3),
            "Struktur_z": round(float(zs[i]), 2),
            "Befund": verdict,
        })

    out_rows.sort(key=lambda r: (r["Befund"].startswith("WIDERSPRUCH") and -1 or 0,
                                 r["RGB_z"]))
    print(f"{len(keys)} Baeume gepaart | RGB '{args.rgb_col}' vs Struktur '{sname}'")
    print(f"Spearman rho = {rho:+.3f}  (Erwartung: positiv, wenn beide dieselbe "
          f"Vitalitaet messen)")
    print(f"Bestaetigt: {agree}   Widerspruch: {contra}   "
          f"uebrig unauffaellig: {len(keys) - agree - contra}")
    for r in out_rows:
        if r["Befund"].startswith("WIDERSPRUCH"):
            print(f"  ! {r['key']}: RGB_z {r['RGB_z']:+.2f}  Struktur_z "
                  f"{r['Struktur_z']:+.2f}  -> {r['Befund']}")

    if args.out:
        fields = ["key", "RGB", "RGB_z", sname, "Struktur_z", "Befund"]
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(out_rows)
        print(f"-> {args.out}")


if __name__ == "__main__":
    main()
