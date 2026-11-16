#!/usr/bin/env python3
"""qforest_qsm.py -- Was der Bodenscanner in der Krone verpasst: QSM-Vergleich, ein Baum.

Daten: D'hont, Calders et al., grosse alte Tropenbaeume, Zenodo 15880857 (CC BY 4.0,
Q-ForestLab). Je Baum zwei Aufnahmen: nur Bodenscan (TLS) und Boden + Kronenscan
(CLS+TLS, Scanner in der Krone), je als Holzpunktwolke und als TreeQSM (10 Laeufe).

Ausgabe:
  * extdata/qforest/<baum>_qsm_vergleich.json  Kennwerte beider QSMs (Mittel, Streuung
    ueber die 10 Laeufe): Volumen, Astzahl, Astlaenge, Astwinkel
  * Szene qforest-qsm-<baum> in platform/dev-data: Stufen "Nur Bodenscan" und
    "Boden + Kronenscan", Einfaerbung "Nur vom Kronenscan" (Punkte ohne Bodenscan-
    Punkt im Umkreis von 5 cm), QSM-Zylinder des CLS+TLS-Modells

  python scripts/qforest_qsm.py BRA --data data/qforest/qsm --lat -3.0 --lon -60.0
"""
import argparse
import json
import math
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy.io as sio
from PIL import Image
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
MEDIA = REPO / "platform" / "dev-data" / "media"
ZEN = "https://zenodo.org/records/15880857/files/{}?download=1"
MAXPTS = 700_000
ONLY_CLS = (240, 140, 60)
BOTH = (120, 150, 190)
RAMP = [[150, 108, 68], [150, 130, 70], [120, 165, 80], [100, 190, 95], [150, 215, 120]]


def fetch(name, data):
    p = data / name
    if not p.exists():
        print(f"  lade {name} ...", flush=True)
        urllib.request.urlretrieve(ZEN.format(name), p)
    return p


def read_xyz(path):
    with open(path) as fh:
        first = fh.readline()
    sep = "," if "," in first else None
    try:
        import pandas as pd
        df = pd.read_csv(path, sep=sep or r"\s+", header=None, usecols=[0, 1, 2],
                         engine="c" if sep else "python", comment="/")
        return df.to_numpy(np.float64)
    except Exception:
        return np.loadtxt(path, delimiter=sep, usecols=(0, 1, 2))


def qsm_stats(path):
    Q = np.atleast_1d(sio.loadmat(path, squeeze_me=True, struct_as_record=False)["QSMs"])
    rows = []
    for q in Q:
        td, br = q.treedata, q.branch
        order = np.atleast_1d(br.order)
        ang = np.atleast_1d(br.angle).astype(float)
        first = (order == 1) & np.isfinite(ang)
        rows.append({
            "Gesamtvolumen_L": float(td.TotalVolume), "Astvolumen_L": float(td.BranchVolume),
            "Stammvolumen_L": float(td.TrunkVolume), "Astlaenge_m": float(td.BranchLength),
            "Aeste": int(td.NumberBranches), "max_Astordnung": int(td.MaxBranchOrder),
            "Baumhoehe_m": float(td.TreeHeight), "BHD_cm": float(td.DBHqsm) * 100,
            "Astwinkel_1Ordnung_Median_Grad": float(np.median(ang[first])) if first.any() else None,
            "Anteil_steile_Aeste_unter_45Grad": float((ang[first] < 45).mean()) if first.any() else None,
        })
    out = {}
    for k in rows[0]:
        v = np.array([r[k] for r in rows if r[k] is not None], float)
        out[k] = {"mittel": round(float(v.mean()), 2), "sd": round(float(v.std()), 2)}
    return out, Q[0]


def qsm_bin(q, origin, path):
    c = q.cylinder
    s = np.asarray(c.start, float) - origin
    e = s + np.asarray(c.axis, float) * np.asarray(c.length, float)[:, None]
    r = np.asarray(c.radius, float)
    o = np.clip(np.asarray(c.BranchOrder, int), 0, 255).astype(np.uint8)
    path.write_bytes(np.ascontiguousarray(s, "<f4").tobytes() + np.ascontiguousarray(e, "<f4").tobytes()
                     + np.ascontiguousarray(r, "<f4").tobytes() + o.tobytes())
    return len(r), int(o.max())


def height_rgb(z):
    stops = np.array([[52, 92, 58], [70, 140, 70], [140, 190, 85], [225, 225, 140]], float)
    t = np.clip((z - z.min()) / max(np.ptp(z), 1e-6), 0, 1) * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    f = (t - i)[:, None]
    return (stops[i] * (1 - f) + stops[i + 1] * f).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("tree", help="Kuerzel im Datensatz, z. B. BRA, PER1, COL, AUS1")
    ap.add_argument("--data", required=True)
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--where", default="Brasilien (Amazonas)")
    a = ap.parse_args()
    data = Path(a.data)
    data.mkdir(parents=True, exist_ok=True)
    t = a.tree

    st_tls, _ = qsm_stats(fetch(f"{t}_tls_wood_qsm.mat", data))
    st_cls, q_cls = qsm_stats(fetch(f"{t}_clstls_wood_qsm.mat", data))
    gain = {k: round(100 * (st_cls[k]["mittel"] / st_tls[k]["mittel"] - 1), 1)
            for k in ("Gesamtvolumen_L", "Astvolumen_L", "Astlaenge_m", "Aeste")
            if st_tls[k]["mittel"]}
    res = {"baum": t, "quelle": "Zenodo 15880857 (CC BY 4.0)", "laeufe_je_QSM": 10,
           "nur_bodenscan": st_tls, "boden_plus_kronenscan": st_cls,
           "zuwachs_durch_kronenscan_prozent": gain}
    out = REPO / "extdata" / "qforest" / f"{t.lower()}_qsm_vergleich.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"-> {out.name}: Zuwachs durch Kronenscan {gain}")

    tls = read_xyz(fetch(f"{t}_tls_wood.txt", data))
    cls = read_xyz(fetch(f"{t}_clstls_wood.txt", data))
    print(f"  Punkte: Boden {len(tls):,}, Boden+Krone {len(cls):,}")
    origin = np.array([cls[:, 0].mean(), cls[:, 1].mean(), np.percentile(cls[:, 2], 1)])
    rng = np.random.default_rng(0)
    sid = f"qforest-qsm-{t.lower()}"
    dest = MEDIA / "scenes" / sid
    dest.mkdir(parents=True, exist_ok=True)
    tree_tls = cKDTree(tls[rng.choice(len(tls), min(len(tls), 3_000_000), replace=False)])
    levels, share = [], None
    for lid, label, pts in (("tls", "Nur Bodenscan", tls), ("cls", "Boden + Kronenscan", cls)):
        sel = np.sort(rng.choice(len(pts), MAXPTS, replace=False)) if len(pts) > MAXPTS \
            else np.arange(len(pts))
        p = np.ascontiguousarray(pts[sel] - origin, "<f4")
        (dest / f"cloud_{lid}.bin").write_bytes(p.tobytes() + height_rgb(p[:, 2]).tobytes())
        gt = np.empty((len(p), 3), np.uint8)
        gt[:] = BOTH
        if lid == "cls":
            dd, _ = tree_tls.query(pts[sel], distance_upper_bound=0.05)
            only = ~np.isfinite(dd)
            gt[only] = ONLY_CLS
            share = float(only.mean())
        (dest / f"cloud_{lid}_gt.bin").write_bytes(p.tobytes() + gt.tobytes())
        levels.append({"id": lid, "label": label, "bin": f"scenes/{sid}/cloud_{lid}.bin",
                       "bin_gt": f"scenes/{sid}/cloud_{lid}_gt.bin", "count": int(len(p)),
                       "bbox_min": [float(v) for v in p.min(0)],
                       "bbox_max": [float(v) for v in p.max(0)]})
        if lid == "cls":                             # Vorschau: Seitenansicht
            W, H = 640, 480
            img = np.full((H, W, 3), 13, np.uint8)
            sc = min((W - 20) / np.ptp(p[:, 0]), (H - 20) / np.ptp(p[:, 2]))
            nx = ((p[:, 0] - p[:, 0].min()) * sc + (W - sc * np.ptp(p[:, 0])) / 2).astype(int)
            ny = (H - 10 - (p[:, 2] - p[:, 2].min()) * sc).astype(int)
            img[np.clip(ny, 0, H - 1), np.clip(nx, 0, W - 1)] = gt
            Image.fromarray(img).save(dest / "thumb.jpg", quality=82)
    res["punkte_nur_kronenscan_anteil"] = round(share, 3)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    n, omax = qsm_bin(q_cls, origin, dest / "qsm.bin")

    m = lambda d, k: d[k]["mittel"]                   # noqa: E731
    desc = (f"Grosser alter Tropenbaum ({a.where}) aus dem Q-ForestLab-Datensatz zu "
            f"Bodenscan und Kronenscan (D'hont, Calders et al.). Umschalter unten: nur "
            f"Bodenscan gegen Boden + Kronenscan; Einfaerbung 'Nur vom Kronenscan' zeigt "
            f"in Orange, was der Bodenscanner nicht erfasst ({share * 100:.0f} % der Holzpunkte). "
            f"Im Zylindermodell (TreeQSM, Mittel aus 10 Laeufen) bringt der Kronenscan "
            f"{gain.get('Astlaenge_m', 0):+.0f} % Astlaenge, {gain.get('Aeste', 0):+.0f} % Aeste "
            f"und {gain.get('Gesamtvolumen_L', 0):+.0f} % Holzvolumen "
            f"({m(st_tls, 'Gesamtvolumen_L') / 1000:.1f} -> {m(st_cls, 'Gesamtvolumen_L') / 1000:.1f} m3). "
            f"Quelle: Zenodo 15880857, CC BY 4.0.")
    attrs = {"Volumen_nur_Boden_m3": round(m(st_tls, "Gesamtvolumen_L") / 1000, 2),
             "Volumen_mit_Krone_m3": round(m(st_cls, "Gesamtvolumen_L") / 1000, 2),
             "Aeste_nur_Boden": int(m(st_tls, "Aeste")), "Aeste_mit_Krone": int(m(st_cls, "Aeste")),
             "Astlaenge_nur_Boden_m": round(m(st_tls, "Astlaenge_m")),
             "Astlaenge_mit_Krone_m": round(m(st_cls, "Astlaenge_m")),
             "Hoehe_m": round(m(st_cls, "Baumhoehe_m"), 1), "BHD_cm": round(m(st_cls, "BHD_cm"), 1),
             "Astwinkel_Median_Grad": m(st_cls, "Astwinkel_1Ordnung_Median_Grad"),
             "Anteil_steile_Aeste": m(st_cls, "Anteil_steile_Aeste_unter_45Grad")}
    scene = {
        "id": sid, "title": f"Grosser alter Baum, {a.where} — was der Bodenscanner in der Krone verpasst (Q-ForestLab)",
        "description": desc, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pano": None, "thumb": f"scenes/{sid}/thumb.jpg", "width": None, "height": None,
        "variants": [],
        "source": {"type": "qforest-qsm", "origin_xyz": [float(c) for c in origin],
                   "dataset": "Large old trees: terrestrial + canopy laser scanning (D'hont, Calders et al.)",
                   "url": "https://doi.org/10.5281/zenodo.15880857", "license": "CC-BY-4.0"},
        "pointcloud": {**{k: levels[0][k] for k in ("bin", "count", "bbox_min", "bbox_max")},
                       "base_label": "Höhe", "gt_tag": "Boden- vs. Kronenscan",
                       "coloring_labels": {"gt": "Nur vom Kronenscan"}, "levels": levels},
        "qsm": {"bin": f"scenes/{sid}/qsm.bin", "count": n, "order_max": omax, "ramp": RAMP},
        "legend": {"title": "Einfärbungen", "items": [
            {"label": "nur vom Kronenscan erfasst (kein Bodenscan-Punkt im Umkreis von 5 cm)",
             "color": "rgb({},{},{})".format(*ONLY_CLS)},
            {"label": "auch vom Boden erfasst", "color": "rgb({},{},{})".format(*BOTH)}],
            "note": "Stufen unten: Nur Bodenscan / Boden + Kronenscan. QSM-Modell: TreeQSM aus Boden + Kronenscan."},
        "qsm_vergleich": res,
        "markers": [{"id": "baum", "label": f"Baum {t}: Bodenscan vs. Kronenscan",
                     "yaw": 0, "pitch": 0,
                     "xyz": [float(origin[0]), float(origin[1]), float(origin[2] + 1.3)],
                     "attributes": attrs, "demo": False}],
    }
    if a.lat is not None:
        scene["source"]["gps"] = {"lat": a.lat, "lon": a.lon}
    (dest / "scene.json").write_text(json.dumps(scene, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"-> Szene {sid}: {n} Zylinder, Anteil nur Kronenscan {share:.1%}")


if __name__ == "__main__":
    sys.exit(main())
