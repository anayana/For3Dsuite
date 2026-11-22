"""Repraesentativitaet der Stichprobe und Vorschlaege fuer neue Standorte.

* Abdeckung je Variable: Anteil der Gebietsflaeche, deren Wert innerhalb der Spanne an den Punkten liegt,
  plus Vergleich der Verteilungen (Kolmogorov-Smirnov-Abstand).
* Multivariat: Anteil der Flaeche im Gueltigkeitsbereich (AOA).
* Bias: Verteilung des Abstands zu Wegen an den Punkten vs. im Gebiet.
* Vorschlaege: gierige Auswahl der Zellen, die den Gueltigkeitsbereich am staerksten erweitern
  (je neuer Punkt die meiste zusaetzliche Flaeche mit DI <= Schwelle), mit Mindestabstand.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import ks_2samp


def coverage_table(names, X_points, X_area):
    rows = []
    for j, n in enumerate(names):
        p = X_points[:, j][np.isfinite(X_points[:, j])]
        a = X_area[:, j][np.isfinite(X_area[:, j])]
        if len(p) < 2 or len(a) < 2:
            continue
        inside = ((a >= p.min()) & (a <= p.max())).mean()
        ks = ks_2samp(p, a).statistic
        rows.append(dict(variable=n, flaeche_in_spanne=float(inside), ks_abstand=float(ks),
                         punkte_min=float(p.min()), punkte_max=float(p.max()),
                         gebiet_p05=float(np.percentile(a, 5)), gebiet_p95=float(np.percentile(a, 95))))
    return rows


def access_bias(dist_points, dist_area):
    p = dist_points[np.isfinite(dist_points)]
    a = dist_area[np.isfinite(dist_area)]
    if len(p) < 3:
        return None
    ks = ks_2samp(p, a)
    return dict(median_punkte=float(np.median(p)), median_gebiet=float(np.median(a)), ks=float(ks.statistic),
                p_wert=float(ks.pvalue), verzerrt=bool(ks.pvalue < 0.05 and np.median(p) < np.median(a)))


def suggest_sites(aoa_model, X_cells, xy_cells, n=10, min_dist=None, n_eval=4000, n_cand=600, seed=0):
    """Gierige AOA-Erweiterung. Rueckgabe: Liste dict(x, y, gewinn_anteil, di)."""
    rng = np.random.default_rng(seed)
    ok = np.all(np.isfinite(X_cells), 1)
    X, xy = X_cells[ok], xy_cells[ok]
    if len(X) == 0:
        return []
    ev = rng.choice(len(X), min(n_eval, len(X)), replace=False)
    Ze = aoa_model._prep(X[ev])
    d_cur = cKDTree(aoa_model.train_w).query(Ze)[0] / aoa_model.d_bar
    di_all = d_cur.copy()
    # Kandidaten bevorzugt ausserhalb des AOA
    out_idx = ev[d_cur > aoa_model.threshold]
    pool = out_idx if len(out_idx) >= 10 else ev
    cand = rng.choice(pool, min(n_cand, len(pool)), replace=False)
    Zc = aoa_model._prep(X[cand])
    thr = aoa_model.threshold
    chosen = []
    min_dist = min_dist or 0.0
    for _ in range(n):
        # Abstand jeder Evaluationszelle zu jedem Kandidaten im Merkmalsraum (blockweise)
        best_gain, best_k, best_d = -1, None, None
        for s in range(0, len(cand), 100):
            D = np.sqrt(((Ze[:, None, :] - Zc[None, s:s + 100, :]) ** 2).sum(-1)) / aoa_model.d_bar
            newd = np.minimum(d_cur[:, None], D)
            gain = ((newd <= thr).sum(0) - (d_cur <= thr).sum())
            for k in np.argsort(-gain)[:5]:
                gi = cand[s + k]
                if any(np.hypot(*(xy[gi] - xy[c])) < min_dist for c in chosen):
                    continue
                if gain[k] > best_gain:
                    best_gain, best_k, best_d = gain[k], s + k, newd[:, k]
                break
        if best_k is None or best_gain <= 0:
            break
        gi = cand[best_k]
        chosen.append(gi)
        d_cur = best_d
        cand = np.delete(cand, best_k)
        Zc = np.delete(Zc, best_k, 0)
    res = []
    before = (di_all <= thr).mean()
    d_tmp = di_all.copy()
    for gi in chosen:
        z = aoa_model._prep(X[gi:gi + 1])
        d_tmp = np.minimum(d_tmp, np.sqrt(((Ze - z) ** 2).sum(-1)) / aoa_model.d_bar)
        after = (d_tmp <= thr).mean()
        res.append(dict(x=float(xy[gi, 0]), y=float(xy[gi, 1]), aoa_anteil_danach=float(after),
                        gewinn=float(after - before), di=float(aoa_model.di(X[gi:gi + 1])[0])))
        before = after
    return res


def write_suggestions(sites, crs, gpkg_path, gpx_path):
    import geopandas as gpd
    from shapely.geometry import Point
    if not sites:
        return None
    g = gpd.GeoDataFrame([{"nr": i + 1, **s} for i, s in enumerate(sites)],
                         geometry=[Point(s["x"], s["y"]) for s in sites], crs=crs)
    g.to_file(gpkg_path, driver="GPKG")
    w = g.to_crs("EPSG:4326")
    pts = "\n".join(
        f'  <wpt lat="{p.y:.7f}" lon="{p.x:.7f}"><name>BioScale-{r.nr:02d}</name>'
        f'<desc>Gewinn Gueltigkeitsbereich {100 * r.gewinn:.1f} %</desc></wpt>'
        for p, r in zip(w.geometry, w.itertuples()))
    gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="BioScale" '
           'xmlns="http://www.topografix.com/GPX/1/1">\n' + pts + "\n</gpx>\n")
    with open(gpx_path, "w", encoding="utf-8") as f:
        f.write(gpx)
    return g
