import numpy as np
import pytest
from scipy.spatial.distance import cdist

from bioscale import aoa as A


def test_fivenum_like_r():
    # R: fivenum(1:10) -> 1.0 3.0 5.5 8.0 10.0
    assert np.allclose(A.fivenum(np.arange(1, 11)), [1, 3, 5.5, 8, 10])
    # R: fivenum(c(1,2,3,4,100)) -> 1 2 3 4 100
    assert np.allclose(A.fivenum([1, 2, 3, 4, 100]), [1, 2, 3, 4, 100])


def test_boxplot_stats_like_r():
    # R: boxplot.stats(c(1,2,3,4,100))$stats -> 1 2 3 4 4
    assert np.allclose(A.boxplot_stats([1, 2, 3, 4, 100]), [1, 2, 3, 4, 4])
    # R: boxplot.stats(1:10)$stats -> 1.0 3.0 5.5 8.0 10.0
    assert np.allclose(A.boxplot_stats(np.arange(1, 11)), [1, 3, 5.5, 8, 10])


def test_train_di_matches_bruteforce():
    """Gleiche Logik wie CAST::trainDI, unabhaengig per Brute Force nachgerechnet."""
    rng = np.random.default_rng(1)
    X = rng.normal(size=(30, 3)) * [1, 5, 0.1] + [0, 10, 3]
    w = np.array([0.5, 0.3, 0.2])
    folds = np.arange(30) % 3
    m = A.train_di(X, w, folds)
    Z = (X - X.mean(0)) / X.std(0, ddof=1) * w
    D = cdist(Z, Z)
    dbar = D[np.triu_indices(30, 1)].mean()
    assert m.d_bar == pytest.approx(dbar)
    tdi = np.array([D[i, folds != folds[i]].min() for i in range(30)]) / dbar
    assert np.allclose(m.train_di, tdi)
    # neue Daten
    Xn = rng.normal(size=(50, 3)) * [3, 5, 0.1] + [0, 10, 3]
    Zn = (Xn - X.mean(0)) / X.std(0, ddof=1) * w
    di = cdist(Zn, Z).min(1) / dbar
    a, d = m.aoa(Xn)
    assert np.allclose(d, di)
    assert np.array_equal(a, (di <= m.threshold).astype(float))
    assert m.threshold == pytest.approx(A.boxplot_stats(tdi)[4])


def test_weights_scale_invariant():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(20, 2))
    a = A.train_di(X, [1, 2]).di(X + 0.3)
    b = A.train_di(X, [10, 20]).di(X + 0.3)
    assert np.allclose(a, b)


def test_nan_rows_give_nan():
    X = np.random.default_rng(0).normal(size=(10, 2))
    m = A.train_di(X)
    a, d = m.aoa(np.array([[np.nan, 0.0], [0.0, 0.0]]))
    assert np.isnan(a[0]) and np.isfinite(a[1])


@pytest.mark.skipif(True, reason="nur mit R + CAST: test_cast_crosscheck manuell aktivieren")
def test_cast_crosscheck():
    import pandas as pd

    from bioscale import rbridge
    if not rbridge.has_package("CAST"):
        pytest.skip("CAST fehlt")
    rng = np.random.default_rng(3)
    tr = pd.DataFrame(rng.normal(size=(40, 2)), columns=["a", "b"])
    nw = pd.DataFrame(rng.normal(size=(30, 2)) * 2, columns=["a", "b"])
    folds = np.arange(40) % 4 + 1
    ref = rbridge.cast_aoa(tr, nw, {"a": 1.0, "b": 0.5}, folds)
    m = A.train_di(tr.values, [1.0, 0.5], folds)
    assert np.allclose(m.di(nw.values), ref.DI.values, atol=1e-6)
