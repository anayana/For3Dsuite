"""Downloader fuer offene Daten. Kein Google: Suche ueber STAC (Earth Search / Copernicus Data Space),
Rasterzugriff direkt auf Cloud Optimized GeoTIFFs (nur der benoetigte Ausschnitt wird gelesen).

Getestet in dieser Version (Stand siehe KONZEPT.md):
  * Sentinel-2 L2A ueber Earth Search (STAC) + sentinel-cogs (S3, offen)   -> Mock-Tests + echter Abruf
  * Copernicus DEM GLO-30 (S3, offen)                                       -> Mock-Tests + echter Abruf
  * ESA WorldCover 2021 v200 (S3, offen)                                    -> Mock-Tests + echter Abruf
  * DWD CDC Rasterdaten Deutschland (opendata.dwd.de)                       -> Mock-Tests + echter Abruf
  * Sentinel-1: Standard Planetary Computer 'sentinel-1-rtc' (offen, Signierung noetig) -> NUR Mock-Tests
  * Copernicus HRL (Tree Cover Density, Grassland, Small Woody Features): Download nur ueber das
    CLMS-Portal mit Konto; BioScale liest die heruntergeladene Datei (hrl_layer).
"""
from __future__ import annotations

import gzip
import re
import shutil
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np

from ..grid import Grid, read_to_grid
from ..provenance import LayerRecord

EARTH_SEARCH = "https://earth-search.aws.element84.com/v1"
CDSE_STAC = "https://stac.dataspace.copernicus.eu/v1"
PLANETARY_COMPUTER = "https://planetarycomputer.microsoft.com/api/stac/v1"
DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
WORLDCOVER_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
DWD_GRIDS = "https://opendata.dwd.de/climate_environment/CDC/grids_germany"

# Asset-Namen je Katalog
S2_ASSETS = {
    EARTH_SEARCH: dict(blue="blue", green="green", red="red", rededge1="rededge1", nir="nir", swir16="swir16",
                       swir22="swir22", scl="scl"),
    CDSE_STAC: dict(blue="B02_10m", green="B03_10m", red="B04_10m", rededge1="B05_20m", nir="B08_10m",
                    swir16="B11_20m", swir22="B12_20m", scl="SCL_20m"),
}
SCL_BAD = {0, 1, 3, 8, 9, 10, 11}  # keine Daten, gesaettigt, Wolkenschatten, Wolken, Zirrus, Schnee

INDICES = {
    "NDVI": ("nir", "red"),
    "NDRE": ("nir", "rededge1"),
    "NDMI": ("nir", "swir16"),
    "NBR": ("nir", "swir22"),
}

SEASONS = {"fruehjahr": ("03-01", "05-31"), "sommer": ("06-01", "08-31"), "herbst": ("09-01", "11-15")}


def grid_bbox_wgs84(grid: Grid, buffer_m: float = 0.0):
    from pyproj import Transformer
    minx, miny, maxx, maxy = grid.bounds
    tr = Transformer.from_crs(grid.crs, "EPSG:4326", always_xy=True)
    xs = [minx - buffer_m, maxx + buffer_m]
    ys = [miny - buffer_m, maxy + buffer_m]
    lon, lat = tr.transform([xs[0], xs[1], xs[0], xs[1]], [ys[0], ys[0], ys[1], ys[1]])
    return (min(lon), min(lat), max(lon), max(lat))


# ------------------------------------------------------------------ STAC
def _open_client(endpoint):
    from pystac_client import Client
    return Client.open(endpoint)


def search_items(collection, bbox, datetime, endpoint=EARTH_SEARCH, query=None, max_items=300):
    c = _open_client(endpoint)
    s = c.search(collections=[collection], bbox=list(bbox), datetime=datetime, query=query, max_items=max_items)
    return list(s.items())


def _asset_scale(asset, item=None):
    """Skalierung/Offset. Earth Search hat bei 'earthsearch:boa_offset_applied' den BOA-Offset
    (Baseline >= 04.00) schon abgezogen, meldet ihn aber noch in raster:bands -> dann Offset 0."""
    rb = asset.extra_fields.get("raster:bands") or [{}]
    scale, off = float(rb[0].get("scale", 1e-4)), float(rb[0].get("offset", 0.0))
    if item is not None and item.properties.get("earthsearch:boa_offset_applied"):
        off = 0.0
    return scale, off


def _read_asset(asset, grid: Grid, resampling="bilinear", sign=None):
    href = sign(asset.href) if sign else asset.href
    return read_to_grid(href, grid, resampling=resampling)


def sentinel2_stack(grid: Grid, start: str, end: str, cloud_max: float = 60, endpoint: str = EARTH_SEARCH,
                    indices=("NDVI", "NDRE", "NDMI"), seasons=None, max_items=120, min_valid=0.2, log=print):
    """Saisonale Mediane von Spektralindizes + Zeitreihe (fuer Intensitaet).

    Rueckgabe: layers {name: array}, records [LayerRecord], series {index: (dates, cube)}
    """
    bbox = grid_bbox_wgs84(grid, 50)
    items = search_items("sentinel-2-l2a", bbox, f"{start}/{end}", endpoint,
                         query={"eo:cloud_cover": {"lt": cloud_max}}, max_items=max_items)
    log(f"Sentinel-2: {len(items)} Szenen gefunden ({start} bis {end}, Wolken < {cloud_max} %).")
    keys = S2_ASSETS.get(endpoint, S2_ASSETS[EARTH_SEARCH])
    need = sorted({b for i in indices for b in INDICES[i]})
    dates, cubes = [], {i: [] for i in indices}
    by_day = {}
    for it in items:  # gleiche Aufnahme in mehreren Kacheln -> pro Tag zusammenfassen
        by_day.setdefault(str(it.datetime.date()), []).append(it)
    for day, its in sorted(by_day.items()):
        band = {b: np.full(grid.shape, np.nan, "float32") for b in need}
        for it in its:
            scl = _read_asset(it.assets[keys["scl"]], grid, "nearest") if keys["scl"] in it.assets else None
            for b in need:
                a = it.assets[keys[b]]
                sc, off = _asset_scale(a, it)
                v = _read_asset(a, grid) * sc + off
                if scl is not None:
                    v[np.isin(scl, list(SCL_BAD)) | ~np.isfinite(scl)] = np.nan
                band[b] = np.where(np.isfinite(band[b]), band[b], v)
        valid = np.isfinite(band[need[0]]).mean()
        if valid < min_valid:
            continue
        dates.append(date.fromisoformat(day))
        for i in indices:
            a, b = INDICES[i]
            with np.errstate(invalid="ignore", divide="ignore"):
                cubes[i].append(np.clip((band[a] - band[b]) / (band[a] + band[b]), -1, 1))
    log(f"Sentinel-2: {len(dates)} brauchbare Aufnahmetage.")
    layers, records, series = {}, [], {}
    seasons = seasons or SEASONS
    years = sorted({d.year for d in dates})
    for i in indices:
        if not cubes[i]:
            continue
        cube = np.stack(cubes[i])
        series[i] = (dates, cube)
        for sname, (s0, s1) in seasons.items():
            sel = [k for k, d in enumerate(dates) if any(f"{y}-{s0}" <= d.isoformat() <= f"{y}-{s1}" for y in years)]
            if not sel:
                continue
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                med = np.nanmedian(cube[sel], axis=0)
            nm = f"s2_{i.lower()}_{sname}"
            layers[nm] = med.astype("float32")
            records.append(LayerRecord(name=nm, source="Sentinel-2 L2A (Copernicus), STAC " + endpoint, group="spectral",
                                       origin=endpoint, license="Copernicus open data (frei)",
                                       date_range=f"{start}/{end}",
                                       processing=[f"SCL-Maske {sorted(SCL_BAD)}", f"{i} je Szene",
                                                   f"Median {sname} ({len(sel)} Szenen)"]))
    return layers, records, series


def sentinel1_stack(grid: Grid, start: str, end: str, endpoint: str = PLANETARY_COMPUTER,
                    collection: str = "sentinel-1-rtc", sign=None, seasons=None, max_items=120, log=print):
    """Saisonale Statistik von Sentinel-1 (VV, VH in dB, VH/VV, zeitliche Streuung).

    UNGETESTET gegen echte Server (nur Mock-Tests). Planetary Computer verlangt signierte URLs:
    `sign` = Funktion href -> signierte href (z. B. planetary_computer.sign).
    """
    bbox = grid_bbox_wgs84(grid, 50)
    items = search_items(collection, bbox, f"{start}/{end}", endpoint, max_items=max_items)
    log(f"Sentinel-1: {len(items)} Szenen gefunden.")
    if sign is None and endpoint == PLANETARY_COMPUTER:
        try:
            import planetary_computer
            sign = planetary_computer.sign
        except ImportError:
            log("Hinweis: Paket 'planetary-computer' fehlt - URLs werden unsigniert gelesen.")
    dates, vv, vh = [], [], []
    for it in sorted(items, key=lambda i: i.datetime):
        if "vv" not in it.assets or "vh" not in it.assets:
            continue
        a = _read_asset(it.assets["vv"], grid, sign=sign)
        b = _read_asset(it.assets["vh"], grid, sign=sign)
        if np.isfinite(a).mean() < 0.2:
            continue
        dates.append(it.datetime.date()); vv.append(a); vh.append(b)
    layers, records = {}, []
    if not dates:
        return layers, records, {}
    with np.errstate(divide="ignore", invalid="ignore"):
        VV = 10 * np.log10(np.where(np.stack(vv) > 0, np.stack(vv), np.nan))
        VH = 10 * np.log10(np.where(np.stack(vh) > 0, np.stack(vh), np.nan))
    years = sorted({d.year for d in dates})
    import warnings
    for sname, (s0, s1) in (seasons or SEASONS).items():
        sel = [k for k, d in enumerate(dates) if any(f"{y}-{s0}" <= d.isoformat() <= f"{y}-{s1}" for y in years)]
        if not sel:
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            stats = {f"s1_vv_{sname}": np.nanmean(VV[sel], 0), f"s1_vh_{sname}": np.nanmean(VH[sel], 0),
                     f"s1_vhvv_{sname}": np.nanmean(VH[sel] - VV[sel], 0), f"s1_vh_sd_{sname}": np.nanstd(VH[sel], 0)}
        for nm, arr in stats.items():
            layers[nm] = arr.astype("float32")
            records.append(LayerRecord(name=nm, source=f"Sentinel-1 ({collection}), STAC {endpoint}", group="structure",
                                       origin=endpoint, license="Copernicus open data (frei)", date_range=f"{start}/{end}",
                                       processing=["dB", f"Statistik {sname} ({len(sel)} Szenen)"]))
    return layers, records, {"VH": (dates, VH)}


# ------------------------------------------------------------------ DEM
def dem_tile_url(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    name = f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
    return f"{DEM_BASE}/{name}/{name}.tif"


def _tiles(bbox, step):
    lo0, la0, lo1, la1 = bbox
    out = []
    for la in range(int(np.floor(la0 / step) * step), int(np.floor(la1 / step) * step) + 1, step):
        for lo in range(int(np.floor(lo0 / step) * step), int(np.floor(lo1 / step) * step) + 1, step):
            out.append((la, lo))
    return out


def mosaic_to_grid(urls, grid: Grid, resampling="bilinear"):
    out = np.full(grid.shape, np.nan, "float32")
    for u in urls:
        try:
            a = read_to_grid(u, grid, resampling=resampling)
        except Exception as e:  # Kachel ueber Meer fehlt bei DEM
            if "No such file" in str(e) or "HTTP" in str(e) or "not recognized" in str(e) or "does not exist" in str(e):
                continue
            raise
        out = np.where(np.isfinite(out), out, a)
    return out


def copernicus_dem(grid: Grid):
    urls = [dem_tile_url(la, lo) for la, lo in _tiles(grid_bbox_wgs84(grid, 100), 1)]
    elev = mosaic_to_grid(urls, grid)
    rec = LayerRecord(name="elevation", source="Copernicus DEM GLO-30", group="topography", origin=DEM_BASE,
                      license="Copernicus DEM GLO-30, frei (Lizenzbedingungen ESA/Copernicus)", processing=["bilinear auf Analyseraster"])
    return elev, rec


def terrain(elev: np.ndarray, res: float):
    """Hangneigung (Grad), Nordexposition (cos), Ostexposition (sin), TWI."""
    z = np.where(np.isfinite(elev), elev, np.nanmean(elev))
    gy, gx = np.gradient(z, res)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    aspect = np.arctan2(-gx, gy)  # 0 = Nord
    north, east = np.cos(aspect), np.sin(aspect)
    acc = flow_accumulation_d8(z) * res * res
    tanb = np.tan(np.radians(np.clip(slope, 0.1, None)))
    twi = np.log((acc / res) / tanb)
    m = ~np.isfinite(elev)
    for a in (slope, north, east, twi):
        a[m] = np.nan
    return dict(slope=slope.astype("float32"), northness=north.astype("float32"),
                eastness=east.astype("float32"), twi=twi.astype("float32"))


def flow_accumulation_d8(z: np.ndarray) -> np.ndarray:
    """Einfache D8-Flussakkumulation (Zellenanzahl inkl. eigener Zelle)."""
    h, w = z.shape
    pad = np.pad(z, 1, mode="edge")
    offs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    dist = np.array([np.hypot(a, b) for a, b in offs])
    drops = np.stack([(z - pad[1 + a:1 + a + h, 1 + b:1 + b + w]) / d for (a, b), d in zip(offs, dist)])
    best = np.argmax(drops, 0)
    has = np.max(drops, 0) > 0
    rr, cc = np.mgrid[0:h, 0:w]
    tr = rr + np.array([o[0] for o in offs])[best]
    tc = cc + np.array([o[1] for o in offs])[best]
    ok = has & (tr >= 0) & (tr < h) & (tc >= 0) & (tc < w)
    recv = np.where(ok, tr * w + tc, -1).ravel()
    acc = np.ones(h * w)
    order = np.argsort(-z.ravel(), kind="stable")
    for i in order:
        j = recv[i]
        if j >= 0:
            acc[j] += acc[i]
    return acc.reshape(h, w)


# ------------------------------------------------------------------ WorldCover
WORLDCOVER_CLASSES = {10: "Baeume", 20: "Gebuesch", 30: "Grasland", 40: "Acker", 50: "Bebaut", 60: "Offen/karg",
                      70: "Schnee/Eis", 80: "Wasser", 90: "Feuchtgebiet", 95: "Mangroven", 100: "Moos/Flechten"}


def worldcover_tile_url(lat: int, lon: int) -> str:
    ns = "N" if lat >= 0 else "S"
    ew = "E" if lon >= 0 else "W"
    return f"{WORLDCOVER_BASE}/ESA_WorldCover_10m_2021_v200_{ns}{abs(lat):02d}{ew}{abs(lon):03d}_Map.tif"


def worldcover(grid: Grid):
    urls = [worldcover_tile_url(la, lo) for la, lo in _tiles(grid_bbox_wgs84(grid, 50), 3)]
    arr = mosaic_to_grid(urls, grid, resampling="nearest")
    arr[arr == 0] = np.nan
    rec = LayerRecord(name="worldcover", source="ESA WorldCover 10 m 2021 v200", group="landcover",
                      origin=WORLDCOVER_BASE, license="CC BY 4.0 (ESA WorldCover project)",
                      processing=["naechster Nachbar", "Klassen -> Anteile im Wirkradius"])
    return arr, rec


# ------------------------------------------------------------------ HRL (lokale Datei)
HRL_PRODUCTS = {
    "tree_cover_density": dict(valid=(0, 100), group="structure", kind="continuous"),
    "grassland": dict(valid=(0, 1), group="landcover", kind="binary"),
    "small_woody_features": dict(valid=(0, 1), group="landcover", kind="binary"),
}


def hrl_layer(path, product: str, grid: Grid):
    """Copernicus High Resolution Layer aus heruntergeladener Datei (CLMS-Portal, Konto noetig)."""
    spec = HRL_PRODUCTS[product]
    rs = "nearest" if spec["kind"] == "binary" else "bilinear"
    a = read_to_grid(path, grid, resampling=rs)
    lo, hi = spec["valid"]
    a[(a < lo) | (a > hi)] = np.nan
    rec = LayerRecord(name=f"hrl_{product}", source=f"Copernicus HRL {product}", group=spec["group"], origin=str(path),
                      license="Copernicus Land Monitoring Service, frei", processing=[f"gueltig {lo}-{hi}", rs])
    return a, rec, spec


# ------------------------------------------------------------------ DWD
DWD_VARS = {"air_temperature_mean": ("multi_annual/air_temperature_mean", 0.1, "Lufttemperatur Mittel (Grad C)"),
            "precipitation": ("multi_annual/precipitation", 1.0, "Niederschlag (mm)"),
            "vegetation_begin": ("multi_annual/vegetation_begin", 1.0, "Vegetationsbeginn (Tag im Jahr)")}


def _http_get(url, dest=None, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "bioscale/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        if dest is None:
            return r.read()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
    return dest


def dwd_multi_annual(grid: Grid, var: str = "air_temperature_mean", period: str = "1991", annual_code: str = "17",
                     cache_dir="cache/dwd", base=DWD_GRIDS):
    """Langjaehrige Mittel (1 km, Gauss-Krueger 3) aus dem DWD Climate Data Center."""
    sub, scale, label = DWD_VARS[var]
    listing = _http_get(f"{base}/{sub}/").decode("utf-8", "replace")
    files = re.findall(r'href="([^"]+\.asc\.gz)"', listing)
    pick = [f for f in files if period in f and f.endswith(f"_{annual_code}.asc.gz")]
    if not pick:
        raise FileNotFoundError(f"DWD: keine Datei fuer {var} {period} {annual_code}")
    fname = pick[0]
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    gz = cache / fname
    if not gz.exists():
        _http_get(f"{base}/{sub}/{fname}", gz)
    asc = gz.with_suffix("")
    if not asc.exists():
        with gzip.open(gz, "rb") as fi, open(asc, "wb") as fo:
            shutil.copyfileobj(fi, fo)
    import rasterio
    with rasterio.open(asc) as src:
        arr = src.read(1).astype("float32")
        if src.nodata is not None:
            arr[arr == src.nodata] = np.nan
        arr[arr <= -999] = np.nan
        transform = src.transform
    from ..grid import reproject_array
    out = reproject_array(arr * scale, transform, "EPSG:31467", grid, "bilinear", src_nodata=np.nan)
    rec = LayerRecord(name=f"dwd_{var}", source=f"DWD Climate Data Center: {label}", group="climate",
                      origin=f"{base}/{sub}/{fname}", license="DWD Open Data, Namensnennung (Nutzungsbedingungen des DWD pruefen)",
                      processing=["1 km Raster (EPSG:31467)", "bilinear auf Analyseraster"])
    return out, rec
