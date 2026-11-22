import laspy
import numpy as np
import pytest

from bioscale.covariates import als
from bioscale.grid import Grid

G = Grid("EPSG:25832", 600000, 5650100, 10, 10, 10)  # 100 x 100 m


def make_cloud(path, seed=0):
    """Schraeger Boden, Wald (Baeume 25 m) in der Westhaelfte, Luecke im Osten, LAZ."""
    rng = np.random.default_rng(seed)
    n = 40000
    x = rng.uniform(600000, 600100, n)
    y = rng.uniform(5650000, 5650100, n)
    ground = 300 + 0.1 * (x - 600000)
    pts_x, pts_y, pts_z, cls, rn = [x], [y], [ground], [np.full(n, 2)], [np.full(n, 1)]
    for tx in np.arange(600005, 600050, 10):
        for ty in np.arange(5650005, 5650100, 10):
            m = 600
            r = rng.uniform(0, 4, m)
            a = rng.uniform(0, 2 * np.pi, m)
            h = 25 - r * 2.5 + rng.normal(0, 0.3, m)
            px, py = tx + r * np.cos(a), ty + r * np.sin(a)
            pts_x.append(px); pts_y.append(py); pts_z.append(300 + 0.1 * (px - 600000) + h)
            cls.append(np.full(m, 5)); rn.append(np.full(m, 1))
    hdr = laspy.LasHeader(point_format=1, version="1.2")
    hdr.scales = [0.01, 0.01, 0.01]
    hdr.offsets = [600000, 5650000, 0]
    las = laspy.LasData(hdr)
    las.x, las.y, las.z = map(np.concatenate, (pts_x, pts_y, pts_z))
    las.classification = np.concatenate(cls).astype(np.uint8)
    las.return_number = np.concatenate(rn).astype(np.uint8)
    las.number_of_returns = np.ones(len(las.x), np.uint8)
    las.write(str(path))
    return path


def test_als_metrics(tmp_path):
    p = make_cloud(tmp_path / "wald.laz")
    out, recs, extra = als.als_metrics([p], G, res=1.0, log=lambda *a: None)
    assert {"als_chm_p95", "als_gap_fraction", "als_fhd", "als_canopy_cover", "als_chm_sd"} <= set(out)
    h, gap = out["als_chm_p95"], out["als_gap_fraction"]
    west, east = np.s_[:, 1:4], np.s_[:, 6:]
    assert np.nanmean(h[west]) == pytest.approx(24, abs=2.5)
    assert np.nanmean(h[east]) < 1
    assert np.nanmean(gap[east]) > 0.95 and np.nanmean(gap[west]) < 0.7
    assert np.nanmean(out["als_canopy_cover"][east]) < 0.05
    # Gelaendemodell folgt dem Hang
    dtm = extra["dtm"]
    assert dtm[50, 90] - dtm[50, 10] == pytest.approx(8, abs=0.5)
    assert all(r.group == "structure" for r in recs)


def test_chm_from_drone(tmp_path):
    chm = np.zeros((100, 100)); chm[:, :50] = 30
    m = als.chm_metrics(chm, G, 1.0)
    assert m["chm_p95"][0, 0] == 30 and m["gap_fraction"][0, 9] == 1
