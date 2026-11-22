"""Nachweis der Kernidee an der virtuellen Art (Wahrheit bekannt)."""
import numpy as np

from bioscale import aoa as A
from bioscale import model as M
from bioscale import validate as V
from bioscale.multiscale import focal_mean

RADII = [25, 50, 100, 150, 200, 300, 500, 800]


def _ds(w):
    s = w.sites
    y = s[[c for c in s.columns if c.startswith("visit")]].max(axis=1).values.astype(float)
    return M.Dataset(y, s[["x", "y"]].values, np.ones(len(s)), "presence_absence")


def _pred_xy(w):
    X, Y = w.grid.cell_centers()
    return np.column_stack([X.ravel(), Y.ravel()])


def test_radius_recovered(world):
    """Der wahre Wirkradius (200 m) wird ungefaehr wiedergefunden und liegt in der plausiblen Spanne."""
    ds = _ds(world)
    folds, _ = V.knndm_folds(ds.xy, _pred_xy(world), 5, seed=0)
    feats = {r: world.grid.sample(focal_mean(world.layers["forest"], r, world.grid.res), ds.xy[:, 0], ds.xy[:, 1])
             for r in RADII}
    res = M.select_radius("forest", RADII, feats, ds, folds)
    true = world.truth["true_radius_m"]
    assert true / 1.5 <= res.best <= true * 1.5, res
    assert res.plausible[0] <= true <= res.plausible[1]
    # deutlich besser als sehr kleine und sehr grosse Radien
    sc = dict(zip(RADII, res.scores))
    assert sc[res.best] > sc[25] and sc[res.best] > sc[800]


def test_aoa_flags_extrapolation(world):
    """Stichprobe nur im Westen, Hoehengradient nach Osten: der AOA schliesst den Osten aus."""
    ds = _ds(world)
    xy = ds.xy
    feats = ["forest", "elevation"]
    Xp = np.column_stack([world.grid.sample(focal_mean(world.layers[f], 200, 10), xy[:, 0], xy[:, 1]) for f in feats])
    folds, _ = V.knndm_folds(xy, _pred_xy(world), 5)
    am = A.train_di(Xp, [1.0, 1.0], folds)
    Xc = np.column_stack([focal_mean(world.layers[f], 200, 10).ravel() for f in feats])
    inside, di = am.aoa(Xc)
    inside = inside.reshape(world.grid.shape)
    X, _ = world.grid.cell_centers()
    xn = (X - X.min()) / (X.max() - X.min())
    west = np.nanmean(inside[xn < 0.45])
    far_east = np.nanmean(inside[xn > 0.85])
    assert west > 0.9
    assert far_east < 0.2
    # Extrapolation ist dort, wo die Wahrheit schlecht getroffen wird: DI hoeher im Osten
    assert np.nanmean(di.reshape(world.grid.shape)[xn > 0.85]) > 3 * np.nanmean(di.reshape(world.grid.shape)[xn < 0.45])


def test_spatial_cv_more_pessimistic(world):
    """Naiver Black-Box-Ansatz (Random Forest, alle Layer x alle Radien): zufaellige CV ist optimistischer."""
    ds = _ds(world)
    folds, _ = V.knndm_folds(ds.xy, _pred_xy(world), 5, seed=42)
    fr = V.random_folds(len(ds.y), 5, seed=42)
    Xa = np.column_stack([world.grid.sample(focal_mean(world.layers[b], r, 10), ds.xy[:, 0], ds.xy[:, 1])
                          for b in world.layers for r in [25, 50, 100, 200, 400, 800]])
    sp = V.binary_metrics(ds.y, M.cv_predict("rf", Xa, ds, folds))
    rd = V.binary_metrics(ds.y, M.cv_predict("rf", Xa, ds, fr))
    assert rd["AUC"] > sp["AUC"]
    assert rd["Deviance"] < sp["Deviance"]


def test_knndm_matches_prediction_distances(world):
    """kNNDM-Folds bilden die Vorhersage-Abstaende besser ab als zufaellige Folds."""
    ds = _ds(world)
    _, info = V.knndm_folds(ds.xy, _pred_xy(world), 5)
    assert info["W"] < info["W_random"]
    assert not info["is_random"]
