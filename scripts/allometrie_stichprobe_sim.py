#!/usr/bin/env python3
"""Wie viele gefällte Buchen braucht eine standortspezifische Biomasse-Allometrie?

Monte-Carlo-Simulation (nur numpy). Frage: Wie genau wird die oberirdische
Biomasse eines alten Buchenbestands geschätzt, wenn die Allometrie aus n
gefällten und gewogenen Buchen abgeleitet wird?

Modell (log-linear):  ln M = alpha + b * (ln D - ln 40) + e,  e ~ N(0, sigma^2)
  M  = oberirdische Trockenmasse je Baum [kg], D = BHD [cm]
  Literaturfunktion: Jenkins et al. 2003 (Laubholz), umgestellt auf ln D - ln 40.

Wahre Standortfunktion weicht von der Literatur ab:
  alpha_wahr = alpha_lit + N(0, SD_ALPHA^2)   (Niveau, z. B. Alter, Kronenform)
  b_wahr     = b_lit     + N(0, SD_B^2)       (Steigung, z. B. große alte Bäume)

Verglichene Schätzer (jeweils mit Rücktransformations-Korrektur exp(s^2/2)):
  lit    : Literaturfunktion ohne lokale Daten
  ratio  : Literaturfunktion mit lokalem Niveau-Faktor (nur alpha geschätzt)
  ols    : vollständig lokal angepasst (alpha und b)
  bayes  : lokal angepasst mit Literatur als Vorinformation (alpha, b)

Stichprobenpläne:
  prop   : Bäume zufällig aus dem Bestand (viele dünne Bäume)
  strat  : gleich viele Bäume je BHD-Klasse 10-100 cm (starke Bäume übervertreten)

Ergebnis: relativer RMSE und Bias der Bestandessumme (Vorrat je ha).
Aufruf:  python3 scripts/allometrie_stichprobe_sim.py
"""
import json
import os

import numpy as np

RNG = np.random.default_rng(20261124)
REPS = 4000
NS = [5, 10, 15, 20, 25, 30, 40, 50]
SIGMAS = [0.15, 0.25]          # Reststreuung je Baum (log), ca. 15 % bzw. 25 %
SD_ALPHA, SD_B = 0.20, 0.10     # Abweichung Standort gegen Literatur
PRIOR_SD_ALPHA, PRIOR_SD_B = 0.30, 0.15   # Vorinformation (bewusst weiter)
LN40 = np.log(40.0)
B_LIT = 2.4342
ALPHA_LIT = -2.0127 + B_LIT * LN40


def stand():
    """Synthetischer alter Buchenbestand, 1 ha, BHD >= 7 cm.

    Mischung aus Unter-/Zwischenstand (exponentiell) und Oberstand (normal).
    Liefert ca. 330 Bäume/ha und ca. 33 m2/ha Grundfläche.
    """
    r = np.random.default_rng(7)
    small = 7 + r.exponential(9.0, 200)
    large = r.normal(58, 16, 130)
    d = np.concatenate([small, large])
    return np.clip(d[(d >= 7)], 7, 110)


D_STAND = stand()
X_STAND = np.log(D_STAND) - LN40


def design(kind, n):
    if kind == "prop":
        return RNG.choice(D_STAND, n, replace=True)
    # gleich verteilt über 9 Klassen 10-100 cm, Rest zufällig auf Klassen
    edges = np.linspace(10, 100, 10)
    k = len(edges) - 1
    per = np.full(k, n // k)
    per[RNG.choice(k, n - per.sum(), replace=False)] += 1
    return np.concatenate([RNG.uniform(edges[i], edges[i + 1], per[i]) for i in range(k)])


def fit(kind, x, y, sigma_hat):
    if kind == "lit":
        return ALPHA_LIT, B_LIT
    if kind == "ratio":
        return ALPHA_LIT + np.mean(y - (ALPHA_LIT + B_LIT * x)), B_LIT
    X = np.column_stack([np.ones_like(x), x])
    if kind == "ols":
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        return beta[0], beta[1]
    # bayes: konjugiert normal, sigma als bekannt (Schätzwert) behandelt
    v0inv = np.diag([1 / PRIOR_SD_ALPHA**2, 1 / PRIOR_SD_B**2])
    m0 = np.array([ALPHA_LIT, B_LIT])
    prec = v0inv + X.T @ X / sigma_hat**2
    beta = np.linalg.solve(prec, v0inv @ m0 + X.T @ y / sigma_hat**2)
    return beta[0], beta[1]


def run():
    out = {"annahmen": {
        "baeume_je_ha": int(D_STAND.size),
        "grundflaeche_m2_ha": round(float(np.sum(np.pi / 4 * (D_STAND / 100) ** 2)), 1),
        "anteil_biomasse_bhd_ab_50cm": None,
        "sd_alpha_standort": SD_ALPHA, "sd_b_standort": SD_B,
        "prior_sd_alpha": PRIOR_SD_ALPHA, "prior_sd_b": PRIOR_SD_B,
        "wiederholungen": REPS,
    }, "ergebnis": []}
    m_lit = np.exp(ALPHA_LIT + B_LIT * X_STAND)
    out["annahmen"]["anteil_biomasse_bhd_ab_50cm"] = round(float(m_lit[D_STAND >= 50].sum() / m_lit.sum()), 2)
    for sigma in SIGMAS:
        for plan in ("prop", "strat"):
            for n in NS:
                err = {k: [] for k in ("lit", "ratio", "ols", "bayes")}
                for _ in range(REPS):
                    a_t = ALPHA_LIT + RNG.normal(0, SD_ALPHA)
                    b_t = B_LIT + RNG.normal(0, SD_B)
                    truth = np.sum(np.exp(a_t + b_t * X_STAND + sigma**2 / 2))
                    d = design(plan, n)
                    x = np.log(d) - LN40
                    y = a_t + b_t * x + RNG.normal(0, sigma, n)
                    for k in err:
                        a, b = fit(k, x, y, sigma)
                        if k == "lit":
                            s2 = sigma**2
                        else:
                            res = y - (a + b * x)
                            dof = max(n - (1 if k == "ratio" else 2), 1)
                            s2 = float(res @ res / dof) if k != "bayes" else float(res @ res / max(n - 1, 1))
                        pred = np.sum(np.exp(a + b * X_STAND + s2 / 2))
                        err[k].append(pred / truth - 1)
                row = {"sigma": sigma, "plan": plan, "n": n}
                for k, v in err.items():
                    v = np.asarray(v)
                    row[k] = {"rmse_pct": round(100 * float(np.sqrt(np.mean(v**2))), 1),
                              "bias_pct": round(100 * float(np.mean(v)), 1),
                              "p90_abs_pct": round(100 * float(np.quantile(np.abs(v), 0.9)), 1)}
                out["ergebnis"].append(row)
    return out


if __name__ == "__main__":
    res = run()
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "allometrie_stichprobe_sim.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    a = res["annahmen"]
    print(f"Bestand: {a['baeume_je_ha']} Bäume/ha, G = {a['grundflaeche_m2_ha']} m²/ha, "
          f"Anteil Biomasse BHD>=50 cm: {a['anteil_biomasse_bhd_ab_50cm']}")
    print("sigma plan  n | RMSE% lit ratio ols bayes | p90% ols bayes")
    for r in res["ergebnis"]:
        print(f"{r['sigma']:.2f} {r['plan']:5s} {r['n']:2d} | "
              f"{r['lit']['rmse_pct']:5.1f} {r['ratio']['rmse_pct']:5.1f} {r['ols']['rmse_pct']:5.1f} "
              f"{r['bayes']['rmse_pct']:5.1f} | {r['ols']['p90_abs_pct']:5.1f} {r['bayes']['p90_abs_pct']:5.1f}")
