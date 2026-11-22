"""Downloader: mit Mocks (lokale GeoTIFFs statt Server). Echte Abrufe: test_network_*.py mit BIOSCALE_NETWORK=1."""
import datetime as dt
import gzip

import numpy as np
import pystac
import pytest

from bioscale.covariates import intensity as I
from bioscale.covariates import opendata as OD
from bioscale.grid import Grid

from conftest import write_tif

G = Grid("EPSG:25832", 600000, 5651000, 20, 50, 50)


def test_tile_urls():
    assert OD.dem_tile_url(50, 10).endswith("Copernicus_DSM_COG_10_N50_00_E010_00_DEM/Copernicus_DSM_COG_10_N50_00_E010_00_DEM.tif")
    assert OD.dem_tile_url(-1, -71).split("/")[-1] == "Copernicus_DSM_COG_10_S01_00_W071_00_DEM.tif"
    assert OD.worldcover_tile_url(51, 9).endswith("ESA_WorldCover_10m_2021_v200_N51E009_Map.tif")
    assert OD._tiles((10.2, 50.4, 10.6, 51.2), 1) == [(50, 10), (51, 10)]
    assert OD._tiles((10.2, 50.4, 10.6, 51.2), 3) == [(48, 9), (51, 9)]


class FakeSearch:
    def __init__(self, items):
        self._items = items

    def items(self):
        return iter(self._items)


class FakeClient:
    def __init__(self, items):
        self.items, self.calls = items, []

    def search(self, **kw):
        self.calls.append(kw)
        return FakeSearch(self.items)


def _s2_items(tmp_path, n=6):
    items = []
    rng = np.random.default_rng(0)
    for k in range(n):
        d = dt.datetime(2025, 4 + k, 10)
        assets = {}
        ndvi_target = 0.8 if k != 2 else 0.3  # Mahd im Juni
        red = 800 + rng.integers(0, 20, (60, 60))
        nir = (red * (1 + ndvi_target) / (1 - ndvi_target)).astype(int)
        bands = dict(red=red, nir=nir, rededge1=red * 2, swir16=red * 1.5)
        for b, arr in bands.items():
            p = write_tif(tmp_path / f"{k}_{b}.tif", arr + 1000, 599900, 5651100, 20, dtype="uint16")
            assets[b] = pystac.Asset(str(p), extra_fields={"raster:bands": [{"scale": 1e-4, "offset": -0.1}]})
        scl = np.full((60, 60), 4); scl[:10, :10] = 9  # Wolke
        assets["scl"] = pystac.Asset(str(write_tif(tmp_path / f"{k}_scl.tif", scl, 599900, 5651100, 20, dtype="uint8")))
        it = pystac.Item(f"S2_{k}", None, None, d, {})
        for kk, a in assets.items():
            it.add_asset(kk, a)
        items.append(it)
    return items


def test_sentinel2_stack_mock(tmp_path, monkeypatch):
    items = _s2_items(tmp_path)
    fc = FakeClient(items)
    monkeypatch.setattr(OD, "_open_client", lambda ep: fc)
    layers, recs, series = OD.sentinel2_stack(G, "2025-03-01", "2025-10-31", log=lambda *a: None)
    assert fc.calls[0]["collections"] == ["sentinel-2-l2a"] and fc.calls[0]["query"]["eo:cloud_cover"]["lt"] == 60
    assert "s2_ndvi_sommer" in layers and "s2_ndmi_fruehjahr" in layers
    nd = layers["s2_ndvi_fruehjahr"]
    assert np.nanmedian(nd) == pytest.approx(0.8, abs=0.02)
    dates, cube = series["NDVI"]
    assert len(dates) == 6 and np.isnan(cube[0, 0, 0])  # Wolke maskiert
    assert recs[0].group == "spectral" and "SCL" in recs[0].processing[0]
    il = I.intensity_layers(series)
    assert np.nanmedian(il["int_mahd_ereignisse"]) == 1


def test_boa_offset_flag():
    a = pystac.Asset("x", extra_fields={"raster:bands": [{"scale": 1e-4, "offset": -0.1}]})
    it = pystac.Item("i", None, None, dt.datetime(2024, 1, 1), {"earthsearch:boa_offset_applied": True})
    assert OD._asset_scale(a, it) == (1e-4, 0.0)
    assert OD._asset_scale(a) == (1e-4, -0.1)


def test_sentinel1_stack_mock(tmp_path, monkeypatch):
    items = []
    for k in range(4):
        it = pystac.Item(f"S1_{k}", None, None, dt.datetime(2025, 6, 1 + 5 * k), {})
        it.add_asset("vv", pystac.Asset(str(write_tif(tmp_path / f"vv{k}.tif", np.full((60, 60), 0.1, "float32"), 599900, 5651100, 20))))
        it.add_asset("vh", pystac.Asset(str(write_tif(tmp_path / f"vh{k}.tif", np.full((60, 60), 0.01, "float32"), 599900, 5651100, 20))))
        items.append(it)
    monkeypatch.setattr(OD, "_open_client", lambda ep: FakeClient(items))
    layers, recs, _ = OD.sentinel1_stack(G, "2025-06-01", "2025-08-31", sign=lambda h: h, log=lambda *a: None)
    assert np.nanmean(layers["s1_vv_sommer"]) == pytest.approx(-10, abs=0.01)
    assert np.nanmean(layers["s1_vhvv_sommer"]) == pytest.approx(-10, abs=0.01)


def test_dem_and_terrain_mock(tmp_path, monkeypatch):
    # "Kachel" in WGS84 um das Gebiet
    lon0, lat0, lon1, lat1 = OD.grid_bbox_wgs84(G, 200)
    nx, ny = 200, 200
    res = (lon1 - lon0) / nx
    lon = lon0 + (np.arange(nx) + 0.5) * res
    elev = np.tile(300 + 2000 * (lon - lon0), (ny, 1)).astype("float32")  # Osthang
    p = write_tif(tmp_path / "dem.tif", elev, lon0, lat1, res, crs="EPSG:4326")
    monkeypatch.setattr(OD, "dem_tile_url", lambda la, lo: str(p))
    e, rec = OD.copernicus_dem(G)
    assert np.isfinite(e).all() and e[:, -1].mean() > e[:, 0].mean()
    t = OD.terrain(e, G.res)
    assert np.nanmedian(t["eastness"]) < -0.9  # Hang faellt nach Westen ab -> Exposition West
    assert np.isfinite(t["twi"]).mean() > 0.95


def test_flow_accumulation_valley():
    x = np.abs(np.arange(-10, 11))[None, :] * 1.0
    z = x + np.arange(30)[::-1, None] * 0.1  # V-Tal, nach Sueden geneigt
    acc = I_acc = OD.flow_accumulation_d8(z)
    assert acc[-1, 10] == acc.max() and acc[-1, 10] > 100 and I_acc.min() == 1


def test_worldcover_mock(tmp_path, monkeypatch):
    lon0, lat0, lon1, lat1 = OD.grid_bbox_wgs84(G, 100)
    a = np.full((100, 100), 10, "uint8"); a[:, 50:] = 30
    p = write_tif(tmp_path / "wc.tif", a, lon0, lat1, (lon1 - lon0) / 100, crs="EPSG:4326", nodata=0)
    monkeypatch.setattr(OD, "worldcover_tile_url", lambda la, lo: str(p))
    arr, rec = OD.worldcover(G)
    assert set(np.unique(arr[np.isfinite(arr)])) == {10, 30}
    assert "CC BY" in rec.license


def test_dwd_mock(tmp_path, monkeypatch):
    asc = "ncols 40\nnrows 40\nxllcorner 3580000\nyllcorner 5630000\ncellsize 1000\nNODATA_value -999\n" + \
          "\n".join(" ".join(["85"] * 40) for _ in range(40)) + "\n"
    gz = tmp_path / "src.asc.gz"
    with gzip.open(gz, "wt") as f:
        f.write(asc)
    listing = b'<a href="grids_germany_multi_annual_air_temp_mean_1991_2020_17.asc.gz">x</a>'

    def fake_get(url, dest=None, timeout=60):
        if dest is None:
            return listing
        import shutil
        shutil.copy(gz, dest)
        return dest
    monkeypatch.setattr(OD, "_http_get", fake_get)
    arr, rec = OD.dwd_multi_annual(G, cache_dir=str(tmp_path / "c"))
    assert np.nanmean(arr) == pytest.approx(8.5, abs=1e-4)
    assert rec.group == "climate"


def test_hrl_layer(tmp_path):
    a = np.full((60, 60), 80, "uint8"); a[0, 0] = 255
    p = write_tif(tmp_path / "tcd.tif", a, 599900, 5651100, 20, dtype="uint8")
    arr, rec, spec = OD.hrl_layer(p, "tree_cover_density", G)
    assert np.nanmax(arr) == 80


def test_mowing_events_counts():
    dates = [dt.date(2025, 4, 1) + dt.timedelta(days=12 * k) for k in range(15)]
    ndvi = np.array([0.6, 0.7, 0.8, 0.85, 0.4, 0.6, 0.75, 0.8, 0.35, 0.55, 0.7, 0.72, 0.7, 0.65, 0.6])
    cube = np.stack([np.full((2, 2), v) for v in ndvi])
    cube[:, 1, 1] = 0.8  # Wald: keine Mahd
    cube[6, 0, 0] = np.nan
    ev = I.mowing_events(dates, cube)
    assert ev[0, 1] == 2 and ev[1, 1] == 0 and ev[0, 0] == 2
    assert I.seasonal_amplitude(cube)[1, 1] == pytest.approx(0)
