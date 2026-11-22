"""ALS-/TLS-Punktwolken (LAS/LAZ) -> Strukturmetriken auf dem Analyseraster.

Ablauf
 1. Bodenpunkte (Klasse 2) -> Gelaendemodell (DTM) im Feinraster (Standard 1 m), Luecken interpoliert.
    Fehlt eine Klassifizierung: einfacher Tiefpunktfilter (Minimum je Zelle, geglaettet) - grob!
 2. Normierte Hoehe = z - DTM.
 3. Kronenhoehenmodell (CHM) = Maximum der normierten Hoehe je Feinzelle.
 4. Je Analysezelle: Hoehe (p95, Mittel), Schichtung (Foliage Height Diversity, Shannon ueber Hoehenstufen),
    Deckung > 2 m, Lueckenanteil (CHM < 2 m), Rauigkeit (SD des CHM), Unterwuchs (Anteil 0.5-5 m).
Funktioniert auch mit Drohnen-Oberflaechenmodellen: chm_metrics(dsm - dtm).
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage
from scipy.interpolate import griddata

from ..grid import Grid
from ..provenance import LayerRecord, file_checksum

HEIGHT_BINS = (0.5, 2, 5, 10, 15, 20, 25, 30, 35, 40, 60)


def read_points(path):
    import laspy
    las = laspy.read(path)
    cls = np.asarray(las.classification) if "classification" in las.point_format.dimension_names else None
    rn = np.asarray(las.return_number) if "return_number" in las.point_format.dimension_names else None
    crs = None
    try:
        c = las.header.parse_crs()
        crs = c.to_string() if c else None
    except Exception:
        pass
    return np.asarray(las.x), np.asarray(las.y), np.asarray(las.z), cls, rn, crs


def _bin(x, y, grid: Grid, res):
    c = np.floor((x - grid.x0) / res).astype(int)
    r = np.floor((grid.y0 - y) / res).astype(int)
    W, H = int(np.ceil(grid.width * grid.res / res)), int(np.ceil(grid.height * grid.res / res))
    ok = (r >= 0) & (r < H) & (c >= 0) & (c < W)
    return r, c, ok, H, W


def _cell_reduce(r, c, v, H, W, fn="max"):
    idx = r * W + c
    out = np.full(H * W, np.nan)
    if fn == "max":
        np.fmax.at(out, idx, v)
    elif fn == "min":
        out[:] = np.inf
        np.minimum.at(out, idx, v)
        out[np.isinf(out)] = np.nan
    return out.reshape(H, W)


def dtm_from_points(x, y, z, cls, grid: Grid, res=1.0):
    g = (cls == 2) if cls is not None and (cls == 2).any() else None
    r, c, ok, H, W = _bin(x, y, grid, res)
    if g is not None:
        sel = ok & g
        dtm = _cell_reduce(r[sel], c[sel], z[sel], H, W, "min")
    else:  # grober Tiefpunktfilter
        dtm = _cell_reduce(r[ok], c[ok], z[ok], H, W, "min")
        dtm = ndimage.minimum_filter(np.where(np.isfinite(dtm), dtm, np.inf), size=int(max(3, 10 / res)))
        dtm[np.isinf(dtm)] = np.nan
    # Luecken fuellen
    m = np.isfinite(dtm)
    if m.sum() >= 3 and (~m).any():
        rr, cc = np.nonzero(m)
        qr, qc = np.nonzero(~m)
        fill = griddata(np.column_stack([rr, cc]), dtm[m], np.column_stack([qr, qc]), method="linear")
        near = griddata(np.column_stack([rr, cc]), dtm[m], np.column_stack([qr, qc]), method="nearest")
        dtm[qr, qc] = np.where(np.isfinite(fill), fill, near)
    return dtm


def normalize_heights(x, y, z, dtm, grid: Grid, res=1.0):
    r, c, ok, H, W = _bin(x, y, grid, res)
    hn = np.full(len(z), np.nan)
    hn[ok] = z[ok] - dtm[r[ok], c[ok]]
    return hn


def _agg_factor(grid, res):
    f = grid.res / res
    if abs(f - round(f)) > 1e-6:
        raise ValueError("Analyseraster muss ein ganzzahliges Vielfaches des Feinrasters sein.")
    return int(round(f))


def _blocks(a, f, H, W):
    return a[:H * f, :W * f].reshape(H, f, W, f).transpose(0, 2, 1, 3).reshape(H, W, f * f)


def chm_metrics(chm: np.ndarray, grid: Grid, res=1.0, gap_height=2.0):
    """Metriken aus einem Kronenhoehenmodell (auch Drohne: DSM - DTM)."""
    f = _agg_factor(grid, res)
    H, W = grid.shape
    pad = np.full((H * f, W * f), np.nan)
    hh, ww = min(chm.shape[0], H * f), min(chm.shape[1], W * f)
    pad[:hh, :ww] = chm[:hh, :ww]
    b = _blocks(pad, f, H, W)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        valid = np.isfinite(b).sum(-1)
        out = dict(
            chm_mean=np.nanmean(b, -1),
            chm_p95=np.nanpercentile(b, 95, axis=-1),
            chm_sd=np.nanstd(b, -1),
            gap_fraction=np.where(valid > 0, np.nansum(b < gap_height, -1) / np.maximum(valid, 1), np.nan),
        )
    return {k: v.astype("float32") for k, v in out.items()}


def point_metrics(x, y, hn, rn, grid: Grid, cover_height=2.0):
    """Vertikale Struktur aus den Punkten je Analysezelle."""
    r, c, inside = grid.rowcol(x, y)
    ok = inside & np.isfinite(hn)
    first = ok if rn is None else ok & (rn == 1)
    H, W = grid.shape
    idx = r * W + c
    n_first = np.bincount(idx[first], minlength=H * W).astype(float)
    n_cov = np.bincount(idx[first & (hn > cover_height)], minlength=H * W).astype(float)
    veg = ok & (hn > 0.5)
    bins = np.digitize(hn[veg], HEIGHT_BINS[1:-1])
    nb = len(HEIGHT_BINS) - 1
    counts = np.zeros((H * W, nb))
    np.add.at(counts, (idx[veg], bins), 1)
    tot = counts.sum(1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        p = counts / tot
        fhd = -np.nansum(np.where(p > 0, p * np.log(p), 0), 1)
        under = counts[:, :2].sum(1) / tot[:, 0]  # 0.5-5 m
        cover = n_cov / n_first
    fhd[tot[:, 0] == 0] = np.nan
    cover[n_first == 0] = np.nan
    return dict(canopy_cover=cover.reshape(H, W).astype("float32"),
                fhd=fhd.reshape(H, W).astype("float32"),
                understorey=under.reshape(H, W).astype("float32"))


def als_metrics(paths, grid: Grid, res=1.0, log=print):
    """Ganze Kette fuer eine oder mehrere LAS/LAZ-Dateien. Rueckgabe: {name: array}, [LayerRecord]."""
    paths = [paths] if isinstance(paths, (str, bytes)) or hasattr(paths, "suffix") else list(paths)
    xs, ys, zs, cs, rns = [], [], [], [], []
    for p in paths:
        x, y, z, cls, rn, crs = read_points(p)
        if crs and crs.replace("EPSG:", "") not in grid.crs:
            log(f"Hinweis: {p} hat KBS {crs}, Analyseraster {grid.crs} - bitte gleiche KBS verwenden.")
        xs.append(x); ys.append(y); zs.append(z)
        cs.append(cls if cls is not None else np.full(len(x), 1)); rns.append(rn if rn is not None else np.ones(len(x), int))
    x, y, z, cls, rn = map(np.concatenate, (xs, ys, zs, cs, rns))
    dtm = dtm_from_points(x, y, z, cls, grid, res)
    hn = normalize_heights(x, y, z, dtm, grid, res)
    rr, cc, ok, H, W = _bin(x, y, grid, res)
    chm = _cell_reduce(rr[ok], cc[ok], np.clip(hn[ok], 0, None), H, W, "max")
    out = chm_metrics(chm, grid, res)
    out.update(point_metrics(x, y, hn, rn, grid))
    recs = [LayerRecord(name=f"als_{k}", source="ALS/TLS-Punktwolke (Nutzerdaten)", group="structure",
                        origin=";".join(map(str, paths)), checksum=file_checksum(paths[0]),
                        processing=[f"DTM aus Klasse 2 ({res:g} m)", "normierte Hoehe", f"Metrik {k}"]) for k in out]
    return {f"als_{k}": v for k, v in out.items()}, recs, dict(dtm=dtm, chm=chm)
