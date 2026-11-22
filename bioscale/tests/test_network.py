"""Echte Abrufe offener Daten (nur mit BIOSCALE_NETWORK=1). Kleines Gebiet in Mitteldeutschland."""
import numpy as np
import pytest

from bioscale.covariates import opendata as OD
from bioscale.grid import Grid

pytestmark = pytest.mark.network
G = Grid("EPSG:25832", 535000, 5545000, 20, 50, 50)  # 1 x 1 km, Spessart


def test_real_dem():
    e, _ = OD.copernicus_dem(G)
    assert np.isfinite(e).mean() > 0.99 and 0 < np.nanmean(e) < 1500


def test_real_worldcover():
    a, _ = OD.worldcover(G)
    assert np.isfinite(a).mean() > 0.99 and set(np.unique(a[np.isfinite(a)])) <= set(OD.WORLDCOVER_CLASSES)


def test_real_sentinel2():
    lay, recs, series = OD.sentinel2_stack(G, "2024-05-01", "2024-07-31", cloud_max=30, max_items=8, log=print)
    assert lay and all(np.nanmax(v) <= 1 for v in lay.values())
    # Sommer-NDVI in Mitteleuropa: plausibel 0.3 - 0.95
    assert 0.3 < np.nanmedian(lay["s2_ndvi_sommer"]) < 0.95


def test_real_dwd(tmp_path):
    a, _ = OD.dwd_multi_annual(G, cache_dir=str(tmp_path))
    assert 0 < np.nanmean(a) < 15
