"""Gueltigkeitsbereich (Area of Applicability, AOA) nach Meyer & Pebesma (2021, Methods Ecol. Evol.).

Eigene Python-Umsetzung, die der Logik von CAST::trainDI/aoa folgt:
  1. Praediktoren mit Mittelwert/SD der Trainingsdaten standardisieren,
  2. mit der Variablenwichtigkeit gewichten,
  3. d_bar = mittlerer paarweiser Abstand der Trainingsdaten,
  4. Trainings-DI = Abstand zum naechsten Trainingspunkt AUS EINEM ANDEREN CV-FOLD / d_bar,
  5. Schwelle = oberer Whisker von boxplot.stats(Trainings-DI) (Q3 + 1.5 IQR nach Tukey-Hinges),
  6. Neue Daten: DI = Abstand zum naechsten Trainingspunkt / d_bar;  AOA = DI <= Schwelle.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.distance import pdist


def fivenum(x):
    """Tukeys Fuenf-Punkte-Zusammenfassung wie R stats::fivenum."""
    x = np.sort(np.asarray(x, float)[np.isfinite(x)])
    n = len(x)
    if n == 0:
        return np.full(5, np.nan)
    n4 = np.floor((n + 3) / 2) / 2
    d = np.array([1, n4, (n + 1) / 2, n + 1 - n4, n]) - 1
    return 0.5 * (x[np.floor(d).astype(int)] + x[np.ceil(d).astype(int)])


def boxplot_stats(x, coef=1.5):
    """Wie R grDevices::boxplot.stats(x)$stats."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    s = fivenum(x)
    iqr = s[3] - s[1]
    lo_f, hi_f = s[1] - coef * iqr, s[3] + coef * iqr
    s = s.copy()
    s[0] = x[x >= lo_f].min()
    s[4] = x[x <= hi_f].max()
    return s


@dataclass
class AOAModel:
    mean: np.ndarray
    sd: np.ndarray
    weights: np.ndarray
    train_w: np.ndarray       # standardisiert und gewichtet
    d_bar: float
    train_di: np.ndarray
    threshold: float
    features: list

    def _prep(self, X):
        Z = (np.asarray(X, float) - self.mean) / self.sd
        return Z * self.weights

    def di(self, X):
        X = np.asarray(X, float)
        out = np.full(len(X), np.nan)
        ok = np.all(np.isfinite(X), axis=1)
        if ok.any():
            d, _ = cKDTree(self.train_w).query(self._prep(X[ok]))
            out[ok] = d / self.d_bar
        return out

    def aoa(self, X):
        d = self.di(X)
        return np.where(np.isfinite(d), (d <= self.threshold).astype(float), np.nan), d


def train_di(X, weights=None, folds=None, features=None) -> AOAModel:
    X = np.asarray(X, float)
    mean = X.mean(0)
    sd = X.std(0, ddof=1)
    sd[sd == 0] = 1.0
    w = np.ones(X.shape[1]) if weights is None else np.clip(np.asarray(weights, float), 0, None)
    if w.sum() == 0:
        w = np.ones_like(w)
    T = (X - mean) / sd * w
    d_bar = float(np.mean(pdist(T)))
    if d_bar == 0:
        d_bar = 1.0
    n = len(T)
    dmin = np.full(n, np.inf)
    if folds is None:
        tree = cKDTree(T)
        d, _ = tree.query(T, k=2)
        dmin = d[:, 1]
    else:
        folds = np.asarray(folds)
        for f in np.unique(folds):
            te, tr = folds == f, folds != f
            if tr.any():
                dmin[te] = cKDTree(T[tr]).query(T[te])[0]
    tdi = dmin / d_bar
    thr = float(boxplot_stats(tdi[np.isfinite(tdi)])[4])
    return AOAModel(mean=mean, sd=sd, weights=w, train_w=T, d_bar=d_bar, train_di=tdi, threshold=thr,
                    features=list(features or range(X.shape[1])))
