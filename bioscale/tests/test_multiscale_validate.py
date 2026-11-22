import numpy as np
import pytest

from bioscale import validate as V
from bioscale.multiscale import class_proportion, focal_mean, focal_sd, radius_list, split_feature


def test_focal_mean_constant_and_nan():
    a = np.full((50, 50), 3.0)
    a[10:15, 10:15] = np.nan
    for k in ("gauss", "disk"):
        m = focal_mean(a, 100, 10, k)
        assert np.allclose(m[np.isfinite(m)], 3.0)
        assert np.isfinite(m[12, 12])  # Luecke wird aus Nachbarn gefuellt


def test_focal_mean_smooths_and_conserves():
    a = np.zeros((101, 101)); a[50, 50] = 1
    m = focal_mean(a, 100, 10)
    assert m[50, 50] < 1 and m[50, 50] == m.max()
    assert focal_sd(np.ones((20, 20)), 50, 10).max() < 1e-6


def test_class_proportion():
    c = np.zeros((40, 40)); c[:, 20:] = 10
    p = class_proportion(c, 10, 30, 10)
    assert p[20, 0] < 0.05 and p[20, -1] > 0.95 and 0.3 < p[20, 20] < 0.7


def test_radius_list():
    r = radius_list(10, 500, 8, 20)
    assert r[0] >= 20 and r[-1] <= 500 and r == sorted(set(r))
    assert split_feature("chm@200m") == ("chm", 200.0)


def test_folds_and_metrics():
    rng = np.random.default_rng(0)
    xy = rng.uniform(0, 1000, (100, 2))
    f = V.block_folds(xy, 250, 4)
    assert set(f) <= {0, 1, 2, 3}
    y = (rng.random(100) < 0.5).astype(int)
    m = V.binary_metrics(y, np.where(y == 1, 0.8, 0.2))
    assert m["AUC"] == 1 and m["TSS"] == pytest.approx(1)
    c = V.count_metrics(np.array([0, 1, 2, 5.]), np.array([0.1, 1, 2, 5.]))
    assert c["R2"] > 0.99


def test_boyce_positive_for_good_model():
    rng = np.random.default_rng(1)
    bg = rng.random(2000)
    pres = rng.choice(bg, 300, p=bg / bg.sum())
    assert V.boyce_index(pres, bg) > 0.8
