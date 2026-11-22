"""Raeumliche Pruefung: Block-Kreuzvalidierung, kNNDM, Metriken, Kalibrierung.

Zufaellige Kreuzvalidierung ist bei raeumlich geklumpten Daten zu optimistisch
(Roberts et al. 2017, Ecography; Ploton et al. 2020, Nature Communications).
kNNDM (Linnenbrink et al. 2024) waehlt Folds so, dass die Abstaende Test->Training in der
Kreuzvalidierung denen Vorhersageflaeche->Training entsprechen.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import wasserstein_distance
from sklearn.cluster import KMeans
from sklearn.metrics import roc_auc_score


# ------------------------------------------------------------------ Folds
def random_folds(n, k=5, seed=0):
    rng = np.random.default_rng(seed)
    f = np.arange(n) % k
    rng.shuffle(f)
    return f


def block_folds(xy, block_size, k=5, seed=0):
    """Quadratische Bloecke der Kantenlaenge block_size, zufaellig auf k Folds verteilt."""
    xy = np.asarray(xy)
    bx = np.floor((xy[:, 0] - xy[:, 0].min()) / block_size).astype(int)
    by = np.floor((xy[:, 1] - xy[:, 1].min()) / block_size).astype(int)
    ids = bx * 100000 + by
    u = np.unique(ids)
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(u))
    lut = {b: perm[i] % k for i, b in enumerate(u)}
    return np.array([lut[i] for i in ids])


def _cv_nnd(xy, folds):
    d = np.empty(len(xy))
    for f in np.unique(folds):
        te, tr = folds == f, folds != f
        if tr.sum() == 0:
            d[te] = np.inf
            continue
        d[te] = cKDTree(xy[tr]).query(xy[te])[0]
    return d


def _merge_clusters(labels, k, seed=0):
    """Cluster in k Folds etwa gleicher Groesse zusammenfassen (groesste zuerst)."""
    u, cnt = np.unique(labels, return_counts=True)
    order = np.argsort(-cnt)
    load = np.zeros(k)
    lut = {}
    for i in order:
        j = int(np.argmin(load))
        lut[u[i]] = j
        load[j] += cnt[i]
    return np.array([lut[l] for l in labels])


def knndm_folds(xy, pred_xy, k=5, seed=0, n_candidates=12, max_pred=5000):
    """kNNDM: Folds, deren Test-Training-Abstaende der Vorhersagesituation gleichen.

    Rueckgabe: folds, info (W-Statistik, gewaehlte Clusterzahl, Abstandsverteilungen).
    """
    xy = np.asarray(xy, float)
    pred_xy = np.asarray(pred_xy, float)
    rng = np.random.default_rng(seed)
    if len(pred_xy) > max_pred:
        pred_xy = pred_xy[rng.choice(len(pred_xy), max_pred, replace=False)]
    g_pred = cKDTree(xy).query(pred_xy)[0]
    n = len(xy)
    # Zufalls-CV als Referenz
    f_rand = random_folds(n, k, seed)
    g_rand = _cv_nnd(xy, f_rand)
    best = dict(W=wasserstein_distance(g_pred, g_rand), q=n, folds=f_rand, g_cv=g_rand)
    w_random = best["W"]
    if np.median(g_pred) > np.median(g_rand):
        qs = np.unique(np.round(np.geomspace(k, max(k + 1, n // 2), n_candidates)).astype(int))
        for q in qs:
            lab = KMeans(n_clusters=int(q), n_init=3, random_state=seed).fit_predict(xy)
            f = _merge_clusters(lab, k, seed)
            if len(np.unique(f)) < k:
                continue
            g = _cv_nnd(xy, f)
            W = wasserstein_distance(g_pred, g)
            if W < best["W"]:
                best = dict(W=W, q=int(q), folds=f, g_cv=g)
    info = dict(W=float(best["W"]), W_random=float(w_random), n_clusters=int(best["q"]),
                g_pred=g_pred, g_cv=best["g_cv"], g_random=g_rand,
                is_random=bool(best["q"] == n))
    return best["folds"], info


# ------------------------------------------------------------------ Metriken
def tss_max(y, p):
    y = np.asarray(y)
    best = -1.0
    for t in np.unique(np.quantile(p, np.linspace(0.01, 0.99, 99))):
        pred = p >= t
        sens = (pred & (y == 1)).sum() / max((y == 1).sum(), 1)
        spec = (~pred & (y == 0)).sum() / max((y == 0).sum(), 1)
        best = max(best, sens + spec - 1)
    return float(best)


def boyce_index(pred_presence, pred_background, n_windows=None, width=0.1):
    """Kontinuierlicher Boyce-Index (Hirzel et al. 2006) mit gleitenden Fenstern, Spearman-Korrelation."""
    from scipy.stats import spearmanr
    allp = np.concatenate([pred_presence, pred_background])
    lo, hi = np.nanmin(allp), np.nanmax(allp)
    w = width * (hi - lo)
    starts = np.linspace(lo, hi - w, n_windows or 101)
    pe, mids = [], []
    for s in starts:
        P = ((pred_presence >= s) & (pred_presence <= s + w)).mean()
        E = ((pred_background >= s) & (pred_background <= s + w)).mean()
        if E > 0:
            pe.append(P / E)
            mids.append(s + w / 2)
    if len(pe) < 3 or np.nanstd(pe) == 0:
        return float("nan")
    return float(spearmanr(mids, pe).statistic)


def binary_metrics(y, p, background_p=None):
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    out = {}
    if len(np.unique(y)) == 2:
        out["AUC"] = float(roc_auc_score(y, p))
        out["TSS"] = tss_max(y, p)
    out["Deviance"] = float(-2 * np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
    out["Brier"] = float(np.mean((p - y) ** 2))
    bg = p[y == 0] if background_p is None else background_p
    out["Boyce"] = boyce_index(p[y == 1], bg)
    out["Kalibrierung_Steigung"] = calibration_slope(y, p)
    return out


def count_metrics(y, mu):
    from scipy.stats import spearmanr
    y, mu = np.asarray(y, float), np.clip(np.asarray(mu, float), 1e-9, None)
    ss_res = np.sum((y - mu) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    with np.errstate(divide="ignore", invalid="ignore"):
        dev = 2 * np.sum(np.where(y > 0, y * np.log(y / mu), 0) - (y - mu))
        dev0 = 2 * np.sum(np.where(y > 0, y * np.log(y / y.mean()), 0) - (y - y.mean()))
    return {"R2": float(1 - ss_res / ss_tot) if ss_tot > 0 else float("nan"),
            "Deviance_erklaert": float(1 - dev / dev0) if dev0 > 0 else float("nan"),
            "Spearman": _spearman(y, mu)}


def _spearman(a, b):
    from scipy.stats import spearmanr
    if np.std(a) == 0 or np.std(b) == 0:
        return float("nan")
    return float(spearmanr(a, b).statistic)


def calibration_slope(y, p):
    """Steigung einer logistischen Regression von y auf logit(p). 1 = gut, < 1 = zu extrem."""
    from sklearn.linear_model import LogisticRegression
    if len(np.unique(y)) < 2:
        return float("nan")
    lp = np.log(p / (1 - p)).reshape(-1, 1)
    m = LogisticRegression(C=1e6, max_iter=1000).fit(lp, y)
    return float(m.coef_[0, 0])


def calibration_table(y, p, bins=5):
    q = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    idx = np.clip(np.digitize(p, q[1:-1]), 0, len(q) - 2)
    return [dict(vorhergesagt=float(p[idx == i].mean()), beobachtet=float(np.asarray(y)[idx == i].mean()),
                 n=int((idx == i).sum())) for i in range(len(q) - 1) if (idx == i).any()]


def metrics(dtype, y, p, background_p=None):
    return count_metrics(y, p) if dtype == "counts" else binary_metrics(y, p, background_p)


def main_score(dtype, m):
    """Kennzahl fuer Auswahl (groesser = besser)."""
    if dtype == "counts":
        return m.get("Deviance_erklaert", np.nan)
    return -m.get("Deviance", np.nan)
