"""Occupancy mit Einflussgroessen und Artenzahl - gegen die bekannte Wahrheit."""
import numpy as np
import pandas as pd
import pytest
from scipy.optimize import approx_fprime

from bioscale import model as M
from bioscale import validate as V
from bioscale.multiscale import focal_mean
from bioscale.occurrence import rarefied_richness, richness_sites
from bioscale.synthetic import make_community, make_world


@pytest.fixture(scope="module")
def low_detect():
    return make_world(seed=42, p_detect=0.4)


def _X(w):
    s = w.sites
    return np.column_stack([w.grid.sample(focal_mean(w.layers[b], r, 10), s.x, s.y)
                            for b, r in [("forest", 200), ("elevation", 800)]])


def test_occupancy_corrects_detection(low_detect):
    w = low_detect
    s = w.sites
    V_ = s[[c for c in s.columns if c.startswith("visit")]].values.astype(float)
    X = _X(w)
    true = w.grid.sample(w.psi, s.x, s.y)
    om = M.OccupancyModel().fit(X, V_)
    assert om.p == pytest.approx(0.4, abs=0.06)
    glm = M.Model("glm", "presence_absence").fit(X, V_.max(1))
    mae_occ = np.abs(om.predict(X) - true).mean()
    mae_glm = np.abs(glm.predict(X) - true).mean()
    assert mae_occ < 0.75 * mae_glm                       # Occupancy trifft die wahre Besetzung besser
    assert abs(om.predict(X).mean() - true.mean()) < 0.05  # GLM unterschaetzt systematisch
    assert glm.predict(X).mean() < true.mean() - 0.05


def test_occupancy_gradient():
    """Analytischer Gradient der Likelihood stimmt mit dem numerischen ueberein."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 2))
    V_ = (rng.random((60, 3)) < 0.5).astype(float)
    V_[0, 2] = np.nan
    om = M.OccupancyModel().fit(X, V_)
    D = om.g._design(X)
    K = np.isfinite(V_).sum(1); d = np.nansum(V_, 1)
    th = rng.normal(0, 0.5, D.shape[1] + 1)
    f = lambda t: om._nll(t, D, d, K, d > 0)[0]
    assert np.allclose(om._nll(th, D, d, K, d > 0)[1], approx_fprime(th, f, 1e-6), atol=1e-3)


def test_occupancy_in_cv(low_detect):
    w = low_detect
    s = w.sites
    V_ = s[[c for c in s.columns if c.startswith("visit")]].values.astype(float)
    ds = M.Dataset(V_.max(1), s[["x", "y"]].values, np.ones(len(s)), "presence_absence", visits=V_)
    folds = V.random_folds(len(s), 5, 0)
    p = M.cv_predict("occ", _X(w), ds, folds)
    assert np.all((p >= 0) & (p <= 1))
    assert V.binary_metrics(ds.y, p)["AUC"] > 0.75


def test_rarefaction_exact():
    # 4 Begehungen, Art A in 4, Art B in 1: bei k=1 erwartet 1 + 1/4
    assert rarefied_richness(np.array([4, 1]), 4, 1) == pytest.approx(1.25)
    assert rarefied_richness(np.array([4, 1]), 4, 4) == 2
    assert rarefied_richness(np.array([2, 2, 1]), 3, 2) == pytest.approx(1 + 1 + 2 / 3)


def test_richness_sites_and_filter():
    rows = []
    for loc, (lat, lon) in {"A": (50.0, 9.0), "B": (50.01, 9.0)}.items():
        for v in range(3 if loc == "A" else 2):
            for sp, cls in [("x a", "Aves"), ("y b", "Aves"), ("z c", "Insecta")]:
                if loc == "B" and sp == "y b":
                    continue
                rows.append(dict(scientificName=sp, **{"class": cls}, occurrenceStatus="present", locationID=loc,
                                 eventID=f"{loc}{v}", decimalLatitude=lat, decimalLongitude=lon))
    sites, k, nsp, dropped = richness_sites(pd.DataFrame(rows), "EPSG:25832", {"class": "Aves"})
    assert k == 2 and nsp == 2 and dropped == 0
    s = sites.set_index("locationID")
    assert s.loc["A", "count"] == 2 and s.loc["B", "count"] == 1


def test_community_richness_model():
    w = make_world(seed=42)
    com, truth, params = make_community(w, n_species=20, seed=3)
    sites, k, nsp, _ = richness_sites(com, w.grid.crs)
    assert k == 3 and nsp >= 15
    true_at = w.grid.sample(truth, sites.x, sites.y)
    assert np.corrcoef(sites["count"], true_at)[0, 1] > 0.5
