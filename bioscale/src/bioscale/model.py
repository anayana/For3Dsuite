"""Modelle, Wirkradius-Schaetzung und ehrliche (verschachtelte) raeumliche Pruefung.

Wirkradius: Fuer jede Einflussgroesse wird innerhalb der Profilspanne der Radius gewaehlt, der in
raeumlicher Kreuzvalidierung die beste Vorhersage (kleinste Devianz) liefert (vgl. Jackson & Fahrig
2015). Gegen Ueberanpassung ("so lange probieren, bis es passt"):
  * die Radiuswahl wird in jeder aeusseren Pruef-Falte neu gemacht (verschachtelt),
  * plausible Radien = alle innerhalb 1 Standardfehler vom besten (1-SE-Regel),
  * Warnung, wenn der beste Radius am Rand der Spanne liegt oder die Kurve flach ist,
  * Variablen, die nicht besser als das Nullmodell sind, fliegen raus,
  * hoechstens 1 Variable je 10 Ereignisse, keine Paare mit |r| > 0.7 (Dormann et al. 2013).
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field

import numpy as np
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from . import validate as V

warnings.filterwarnings("ignore", category=UserWarning, module="lightgbm")


def _quad(X):
    return np.hstack([X, X ** 2])


class FastGLM:
    """Ridge-GLM (logistisch oder Poisson) mit linearen + quadratischen Termen, IRLS in numpy.

    Entspricht sklearn LogisticRegression(C=1)/PoissonRegressor mit L2-Strafe auf standardisierten
    Termen, ist aber fuer die vielen kleinen Fits der Radiuswahl ~100x schneller.
    """

    def __init__(self, family="binomial", lam=1.0, max_iter=50):
        self.family, self.lam, self.max_iter = family, lam, max_iter

    def _design(self, X):
        Z = (X - self.mu) / self.sd
        Q = _quad(Z)
        Q = (Q - self.qmu) / self.qsd
        return np.hstack([np.ones((len(Q), 1)), Q])

    def fit(self, X, y, sample_weight=None):
        X = np.asarray(X, float)
        y = np.asarray(y, float)
        w = np.ones(len(y)) if sample_weight is None else np.asarray(sample_weight, float)
        self.mu, self.sd = X.mean(0), X.std(0)
        self.sd[self.sd == 0] = 1.0
        Q = _quad((X - self.mu) / self.sd)
        self.qmu, self.qsd = Q.mean(0), Q.std(0)
        self.qsd[self.qsd == 0] = 1.0
        D = self._design(X)
        p = D.shape[1]
        P = np.eye(p) * self.lam
        P[0, 0] = 0.0
        beta = np.zeros(p)
        if self.family == "binomial":
            m = np.clip(np.average(y, weights=w), 1e-4, 1 - 1e-4)
            beta[0] = np.log(m / (1 - m))
        else:
            beta[0] = np.log(max(np.average(y, weights=w), 1e-6))
        for _ in range(self.max_iter):
            eta = np.clip(D @ beta, -30, 30)
            if self.family == "binomial":
                mu = 1 / (1 + np.exp(-eta))
                W = w * np.clip(mu * (1 - mu), 1e-9, None)
            else:
                mu = np.exp(eta)
                W = w * np.clip(mu, 1e-9, None)
            g = D.T @ (w * (y - mu)) - P @ beta
            H = (D * W[:, None]).T @ D + P
            try:
                step = np.linalg.solve(H, g)
            except np.linalg.LinAlgError:
                step = np.linalg.lstsq(H, g, rcond=None)[0]
            beta = beta + step
            if np.max(np.abs(step)) < 1e-6:
                break
        self.beta = beta
        return self

    def predict_proba(self, X):
        eta = np.clip(self._design(np.asarray(X, float)) @ self.beta, -30, 30)
        p = 1 / (1 + np.exp(-eta))
        return np.column_stack([1 - p, p])

    def predict(self, X):
        eta = np.clip(self._design(np.asarray(X, float)) @ self.beta, -30, 30)
        return np.exp(eta) if self.family == "poisson" else 1 / (1 + np.exp(-eta))


# ------------------------------------------------------------------ Modellfabrik
class Model:
    """Einheitliche Huelle: fit(X, y, w) / predict(X). Fuer Zaehlungen ist y die Rate je Aufwand."""

    def __init__(self, kind: str, dtype: str, seed: int = 0):
        self.kind, self.dtype, self.seed = kind, dtype, seed
        self.m = None

    def _make(self):
        binary = self.dtype != "counts"
        k = self.kind
        if k == "glm":
            return FastGLM("binomial" if binary else "poisson")
        if k == "glm_sklearn":
            core = LogisticRegression(C=1.0, max_iter=2000) if binary else PoissonRegressor(alpha=1e-3, max_iter=2000)
            return make_pipeline(StandardScaler(), FunctionTransformer(_quad), StandardScaler(), core)
        if k == "rf":
            if binary:
                return RandomForestClassifier(n_estimators=200, min_samples_leaf=3, random_state=self.seed, n_jobs=1)
            return RandomForestRegressor(n_estimators=200, min_samples_leaf=3, random_state=self.seed, n_jobs=1)
        if k == "gbm":
            import lightgbm as lgb
            kw = dict(n_estimators=200, learning_rate=0.05, num_leaves=8, min_child_samples=5,
                      subsample=0.8, subsample_freq=1, random_state=self.seed, verbose=-1)
            return lgb.LGBMClassifier(**kw) if binary else lgb.LGBMRegressor(objective="poisson", **kw)
        if k == "maxent":
            try:
                import elapid
                return elapid.MaxentModel(feature_types=["linear", "quadratic", "hinge"], beta_multiplier=1.5)
            except ImportError:  # Ersatz: (gewichtete) logistische Regression ~ Maxent (Fithian & Hastie 2013)
                return make_pipeline(StandardScaler(), FunctionTransformer(_quad), StandardScaler(),
                                     LogisticRegression(C=1.0, max_iter=2000))
        raise ValueError(f"Unbekanntes Modell: {k}")

    def fit(self, X, y, w=None):
        self.m = self._make()
        X = np.asarray(X, float)
        if self.kind == "maxent" and type(self.m).__name__ == "MaxentModel":
            self.m.fit(X, np.asarray(y).astype(int))
            return self
        if len(np.unique(y)) < 2 and self.dtype != "counts":
            self.const = float(np.mean(y))
            self.m = None
            return self
        last = self.m.steps[-1][0] if hasattr(self.m, "steps") else None
        if w is not None:
            kw = {f"{last}__sample_weight": w} if last else {"sample_weight": w}
            self.m.fit(X, y, **kw)
        else:
            self.m.fit(X, y)
        return self

    def predict(self, X):
        X = np.asarray(X, float)
        if self.m is None:
            return np.full(len(X), self.const)
        if self.dtype == "counts":
            return np.clip(self.m.predict(X), 1e-9, None)
        if hasattr(self.m, "predict_proba"):
            return self.m.predict_proba(X)[:, 1]
        return np.asarray(self.m.predict(X)).ravel()  # elapid: cloglog


# ------------------------------------------------------------------ Datensatz
@dataclass
class Dataset:
    y: np.ndarray
    xy: np.ndarray
    effort: np.ndarray
    dtype: str
    weight: np.ndarray | None = None

    @property
    def target(self):
        return self.y / self.effort if self.dtype == "counts" else self.y

    @property
    def fit_weight(self):
        if self.dtype == "counts":
            return self.effort
        return self.weight


def cv_predict(kind, X, ds: Dataset, folds, seed=0):
    p = np.full(len(ds.y), np.nan)
    for f in np.unique(folds):
        te, tr = folds == f, folds != f
        w = None if ds.fit_weight is None else ds.fit_weight[tr]
        m = Model(kind, ds.dtype, seed).fit(X[tr], ds.target[tr], w)
        p[te] = m.predict(X[te])
    if ds.dtype == "counts":
        p = p * ds.effort
    return p


def cv_score(kind, X, ds, folds, seed=0):
    """Mittlerer Score und Standardfehler ueber Folds (groesser = besser)."""
    p = cv_predict(kind, X, ds, folds, seed)
    scores = []
    for f in np.unique(folds):
        te = folds == f
        if ds.dtype != "counts" and len(np.unique(ds.y[te])) < 1:
            continue
        scores.append(V.main_score(ds.dtype, V.metrics(ds.dtype, ds.y[te], p[te])))
    scores = np.array([s for s in scores if np.isfinite(s)])
    return float(np.mean(scores)), float(np.std(scores, ddof=1) / np.sqrt(len(scores))) if len(scores) > 1 else 0.0, p


# ------------------------------------------------------------------ Wirkradius
@dataclass
class RadiusResult:
    base: str
    radii: list
    scores: list
    ses: list
    best: float
    plausible: tuple
    null_score: float
    useful: bool
    warnings: list = field(default_factory=list)


def select_radius(base, radii, feats_by_r: dict, ds: Dataset, folds, seed=0) -> RadiusResult:
    """Univariates GLM je Radius; Wahl per raeumlicher CV, 1-SE-Spanne als Unsicherheit."""
    sc, se = [], []
    for r in radii:
        s, e, _ = cv_score("glm", feats_by_r[r].reshape(-1, 1), ds, folds, seed)
        sc.append(s); se.append(e)
    sc, se = np.array(sc), np.array(se)
    i = int(np.nanargmax(sc))
    null, _, _ = cv_score("glm", np.zeros((len(ds.y), 1)), ds, folds, seed)
    ok = sc >= sc[i] - se[i]
    plaus = (float(np.array(radii)[ok].min()), float(np.array(radii)[ok].max()))
    warn = []
    if i in (0, len(radii) - 1) and len(radii) > 2:
        warn.append(f"{base}: bester Radius ({radii[i]:.0f} m) liegt am Rand der Profilspanne - Spanne pruefen.")
    if ok.mean() > 0.6:
        warn.append(f"{base}: Radius kaum bestimmbar (Kurve flach: {ok.sum()} von {len(radii)} Radien gleich gut).")
    useful = bool(sc[i] - null > se[i])
    return RadiusResult(base, list(map(float, radii)), sc.tolist(), se.tolist(), float(radii[i]), plaus,
                        float(null), useful, warn)


def select_features(bases, radii_by_base, point_feats, ds, folds, max_features, corr_max=0.7, seed=0, min_gain=0.5):
    """Radiuswahl je Variable, dann Nutzen-, Korrelations- und Anzahlfilter.

    point_feats: {(base, r): Werte an den Datenpunkten}
    Rueckgabe: Liste gewaehlter (base, r), Liste RadiusResult, Hinweise
    """
    results, notes = [], []
    for b in bases:
        rr = radii_by_base[b]
        res = select_radius(b, rr, {r: point_feats[(b, r)] for r in rr}, ds, folds, seed)
        results.append(res)
    # Vorwaertsauswahl: Variablen (je im gewaehlten Radius) nur aufnehmen, wenn sie die raeumlich
    # gepruefte Guete gegenueber dem bisherigen Modell verbessern (auch bedingt nuetzliche Variablen).
    order = sorted(results, key=lambda r: -(max(r.scores) - r.null_score))
    chosen, cur = [], None
    for r in order:
        v = point_feats[(r.base, r.best)]
        if any(abs(np.corrcoef(v, point_feats[c])[0, 1]) > corr_max for c in chosen):
            notes.append(f"{r.base}: stark korreliert mit einer wichtigeren Variable (|r| > {corr_max}) - nicht verwendet.")
            continue
        if len(chosen) >= max_features:
            notes.append(f"{r.base}: zu wenige Ereignisse fuer weitere Variablen (Faustregel 10 je Variable) - nicht verwendet.")
            continue
        X = np.column_stack([point_feats[c] for c in chosen] + [v])
        sc, se, _ = cv_score("glm", X, ds, folds, seed)
        ref = r.null_score if cur is None else cur
        if sc - ref > min_gain * max(se, 1e-9):
            chosen.append((r.base, r.best))
            cur = sc
        else:
            notes.append(f"{r.base}: verbessert die raeumlich gepruefte Vorhersage nicht - nicht verwendet.")
    if not chosen:
        best = order[0]
        chosen = [(best.base, best.best)]
        notes.append(f"Keine Variable verbessert die Vorhersage deutlich; {best.base} trotzdem verwendet - Ergebnis kaum belastbar.")
    return chosen, results, notes


def nested_cv(kind, bases, radii_by_base, point_feats, ds: Dataset, folds, max_features, seed=0, inner="same"):
    """Ehrliche Pruefung: Radius- und Variablenwahl in jeder aeusseren Falte neu (nur mit deren Trainingsdaten)."""
    p = np.full(len(ds.y), np.nan)
    chosen_per_fold = []
    for f in np.unique(folds):
        te, tr = folds == f, folds != f
        sub = Dataset(ds.y[tr], ds.xy[tr], ds.effort[tr], ds.dtype, None if ds.weight is None else ds.weight[tr])
        inner_f = folds[tr] if inner == "same" else V.random_folds(tr.sum(), len(np.unique(folds)) - 1, seed)
        _, inner_f = np.unique(inner_f, return_inverse=True)
        pf = {k: v[tr] for k, v in point_feats.items()}
        ch, _, _ = select_features(bases, radii_by_base, pf, sub, inner_f, max_features, seed=seed)
        chosen_per_fold.append(ch)
        Xtr = np.column_stack([point_feats[c][tr] for c in ch])
        Xte = np.column_stack([point_feats[c][te] for c in ch])
        m = Model(kind, ds.dtype, seed).fit(Xtr, sub.target, sub.fit_weight)
        p[te] = m.predict(Xte) * (ds.effort[te] if ds.dtype == "counts" else 1)
    return p, chosen_per_fold


# ------------------------------------------------------------------ Wichtigkeit
def permutation_importance(model: Model, X, ds: Dataset, n_repeats=5, seed=0):
    rng = np.random.default_rng(seed)
    pred = model.predict(X) * (ds.effort if ds.dtype == "counts" else 1)
    base = V.main_score(ds.dtype, V.metrics(ds.dtype, ds.y, pred))
    imp = np.zeros(X.shape[1])
    for j in range(X.shape[1]):
        d = []
        for _ in range(n_repeats):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            pp = model.predict(Xp) * (ds.effort if ds.dtype == "counts" else 1)
            d.append(base - V.main_score(ds.dtype, V.metrics(ds.dtype, ds.y, pp)))
        imp[j] = max(np.mean(d), 0.0)
    if imp.sum() == 0:
        imp[:] = 1.0
    return imp / imp.sum()


def cluster_bootstrap(kind, X, ds: Dataset, Xpred, n_boot=20, seed=0, clusters=None):
    """Unsicherheit: Neuanpassung auf raeumlich gebuendelt gezogenen Stichproben."""
    rng = np.random.default_rng(seed)
    if clusters is None:
        clusters = np.arange(len(ds.y))
    u = np.unique(clusters)
    preds = np.empty((n_boot, len(Xpred)), dtype="float32")
    for b in range(n_boot):
        pick = rng.choice(u, len(u), replace=True)
        idx = np.concatenate([np.flatnonzero(clusters == c) for c in pick])
        w = None if ds.fit_weight is None else ds.fit_weight[idx]
        m = Model(kind, ds.dtype, seed + b).fit(X[idx], ds.target[idx], w)
        preds[b] = m.predict(Xpred)
    return preds
