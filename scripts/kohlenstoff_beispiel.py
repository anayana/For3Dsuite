#!/usr/bin/env python3
"""kohlenstoff_beispiel.py -- exemplarische Kohlenstoffberechnung aus TLS-Daten der Suite.

Bestand: Wienerwald-Buche (SegmentedForests plot_06, ~0,13 ha), Szene
docs/data/scene-segforests-vienna-beech.json. Je Baum liegen vor: BHD, Hoehe,
Kronenmasse, QSM-Holzvolumen (Stamm + Aeste) und die TreeGrOSS-Prognose bis 2056.

Befund vorab: Das Stammvolumen aus dem QSM ist plausibel (Bestandessumme ~ Formzahl-
Schaetzung), das Kronenholz aus dem BELAUBTEN Scan dagegen stark ueberschaetzt (Blaetter
werden als dicke Zylinder modelliert, auch kleine Baeume bekommen > 1 m3). Deshalb:
Stamm aus dem QSM (Formzahl-Kontrolle), Aeste ueber einen Expansionsfaktor.

Drei Wege zur oberirdischen Holzbiomasse:
  1. TLS:          QSM-Stammvolumen x Raumdichte x Ast-Expansionsfaktor
  2. Allometrie:   generische BHD-Funktion (Jenkins et al. 2003, Laubholzgruppe
                   "hard maple/oak/hickory/beech"), wie sie ohne eigene Daten ueblich ist
  3. Lokal kalibriert: V = a * D^b * H^c, an den QSM-Baeumen angepasst
     - log-OLS mit Rueckrechnungskorrektur (Baskerville)
     - nichtlineare Regression (Gauss-Newton) mit heteroskedastischer Varianz
       Var(e) = s^2 * f^(2*delta), delta aus den Residuen geschaetzt (iterativ)
     - dazu ein "ALS-artiges" Modell nur aus Hoehe und Kronendurchmesser
       V = a * (H*CD)^b, um zu zeigen, was Fernerkundung ohne BHD leistet
Danach: Wurzeln, Kohlenstoff, CO2 je ha und die Senke 2026-2056 aus der Prognose.

Annahmen (bewusst als Parameter, mit Spannweite):
  Raumdichte Buche 0,56 t/m3 (0,54-0,58), Ast-Expansion 1,25 (1,15-1,40),
  Kohlenstoffanteil 0,48 (Laubholz), Wurzel/Spross 0,24 (0,20-0,30). Das Suite-QSM ist noch nicht gegen TreeQSM
  validiert (bench_qsm_wytham.py steht aus) -- die QSM-Zahlen sind vorlaeufig.

  python scripts/kohlenstoff_beispiel.py [--out scripts/kohlenstoff_beispiel.json]
"""
import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
SCENE = REPO / "docs" / "data" / "scene-segforests-vienna-beech.json"

RHO, RHO_LO, RHO_HI = 0.56, 0.54, 0.58     # t/m3 Raumdichte Buche
CF = 0.48                                  # Kohlenstoffanteil Laubholz
RS, RS_LO, RS_HI = 0.24, 0.20, 0.30        # Wurzel/Spross
BEF, BEF_LO, BEF_HI = 1.25, 1.15, 1.40     # Stamm -> oberird. Holz (Aeste)
FORMZAHL = 0.5                             # Kontrolle des QSM-Stammvolumens
C2CO2 = 44.0 / 12.0
UBA_EUR_T = 350.0                          # UBA-Klimakostensatz 2026, EUR/t CO2


def jenkins_kg(d_cm):
    """Jenkins et al. 2003, Gruppe hard maple/oak/hickory/beech, oberird. Biomasse in kg."""
    return np.exp(-2.0127 + 2.4342 * np.log(d_cm))


def gauss_newton(X, y, theta, w, iters=60):
    """Gewichtete NLS fuer f = exp(X @ theta) (multiplikatives Potenzmodell)."""
    for _ in range(iters):
        f = np.exp(X @ theta)
        J = f[:, None] * X
        r = y - f
        A = J.T @ (w[:, None] * J)
        g = J.T @ (w * r)
        step = np.linalg.solve(A, g)
        theta = theta + step
        if np.max(np.abs(step)) < 1e-10:
            break
    return theta


def fit_models(X, y):
    """log-OLS (+Baskerville) und heteroskedastische NLS; gibt Parameter und Vorhersagefunktionen."""
    ly = np.log(y)
    beta, *_ = np.linalg.lstsq(X, ly, rcond=None)
    res = ly - X @ beta
    s2 = res @ res / (len(y) - X.shape[1])
    cf = np.exp(s2 / 2)
    theta, delta = beta.copy(), 1.0
    for _ in range(6):                       # Varianzfunktion iterativ schaetzen
        f = np.exp(X @ theta)
        w = f ** (-2 * delta)
        theta = gauss_newton(X, y, theta, w)
        f = np.exp(X @ theta)
        r = np.abs(y - f) + 1e-12
        delta = float(np.polyfit(np.log(f), np.log(r), 1)[0])
        delta = min(max(delta, 0.0), 1.5)
    return {"log_ols": (beta, cf), "nls": (theta, delta)}


def loo_rel_rmse(X, y, kind):
    """Leave-one-out: relativer RMSE und Bias (in % des Mittels)."""
    pred = np.empty_like(y)
    for i in range(len(y)):
        m = np.ones(len(y), bool); m[i] = False
        mods = fit_models(X[m], y[m])
        if kind == "log_ols":
            beta, cf = mods["log_ols"]; pred[i] = np.exp(X[i] @ beta) * cf
        else:
            theta, _ = mods["nls"]; pred[i] = np.exp(X[i] @ theta)
    err = pred - y
    return 100 * np.sqrt(np.mean(err ** 2)) / y.mean(), 100 * err.mean() / y.mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(REPO / "scripts" / "kohlenstoff_beispiel.json"))
    a = ap.parse_args()
    scene = json.loads(SCENE.read_text())
    area = float(scene["stand"]["area_ha"])
    trees = []
    for m in scene["markers"]:
        at = m["attributes"]
        d = at.get("BHD_cm") or at.get("QSM_BHD_cm")
        if not d:
            continue
        trees.append({
            "id": m["id"], "D": float(d), "H": float(at["Hoehe_m"]),
            "CD": float(at.get("Kronendurchmesser_m") or 0),
            "Vwood": (at.get("QSM_Holzvolumen_l") or 0) / 1000.0,
            "V": (at.get("QSM_Stammvolumen_l") or 0) / 1000.0,
            "good": at.get("BHD_Guete") == "good",
            "series": m.get("prognosis_series") or [],
        })
    D = np.array([t["D"] for t in trees]); H = np.array([t["H"] for t in trees])
    CD = np.array([t["CD"] for t in trees]); V = np.array([t["V"] for t in trees])
    Vwood = np.array([t["Vwood"] for t in trees])
    v_ff = np.pi / 4 * (D / 100) ** 2 * H * FORMZAHL
    ratio = np.where(v_ff > 0, V / v_ff, 0)
    has_q = (V > 0) & (ratio > 0.5) & (ratio < 2.0)   # QSM-Stamm plausibel

    # Kalibrierdaten: QSM vorhanden und BHD gut
    cal = has_q & np.array([t["good"] for t in trees]) & (CD > 0)
    Xdh = np.column_stack([np.ones(cal.sum()), np.log(D[cal]), np.log(H[cal])])
    Xals = np.column_stack([np.ones(cal.sum()), np.log(H[cal] * CD[cal])])
    Xh = np.column_stack([np.ones(cal.sum()), np.log(H[cal])])
    y = V[cal]
    m_dh = fit_models(Xdh, y)
    m_als = fit_models(Xals, y)
    m_h = fit_models(Xh, y)
    th_dh, delta_dh = m_dh["nls"]

    def v_dh(d, h):
        return np.exp(th_dh[0] + th_dh[1] * np.log(d) + th_dh[2] * np.log(h))

    # Baumvolumen fuer alle Baeume: QSM wo vorhanden, sonst kalibrierte Allometrie
    V_all = np.where(has_q, V, np.minimum(v_dh(D, H), 2 * v_ff))

    def stand(vol_m3, rho=RHO, rs=RS, bef=BEF):
        agb = vol_m3.sum() * rho * bef / area      # t/ha oberirdisch (Holz)
        tot = agb * (1 + rs)
        c = tot * CF
        return {"AGB_t_ha": agb, "gesamt_t_ha": tot, "C_t_ha": c, "CO2_t_ha": c * C2CO2}

    res_qsm = stand(V_all)
    agb_jenkins = jenkins_kg(D).sum() / 1000 / area
    res_jenkins = {"AGB_t_ha": agb_jenkins, "C_t_ha": agb_jenkins * (1 + RS) * CF}
    res_jenkins["CO2_t_ha"] = res_jenkins["C_t_ha"] * C2CO2

    # Spannweite aus Dichte und Wurzelanteil
    lo = stand(V_all, RHO_LO, RS_LO, BEF_LO)["CO2_t_ha"]
    hi = stand(V_all, RHO_HI, RS_HI, BEF_HI)["CO2_t_ha"]
    qsm_wood_ratio = float(np.median(Vwood[has_q] / V[has_q]))

    # Modellguete (LOO)
    q = {
        "D+H (TLS), log-OLS": loo_rel_rmse(Xdh, y, "log_ols"),
        "D+H (TLS), NLS heteroskedastisch": loo_rel_rmse(Xdh, y, "nls"),
        "H+Kronendurchmesser (ALS-artig), NLS": loo_rel_rmse(Xals, y, "nls"),
        "nur Hoehe, NLS": loo_rel_rmse(Xh, y, "nls"),
    }

    # Senke 2026 -> 2056 aus der TreeGrOSS-Prognose (QSM-verankert)
    years = sorted({p["year"] for t in trees for p in t["series"]})
    traj = []
    for yr in years:
        vol = 0.0
        for i, t in enumerate(trees):
            pts = {p["year"]: p for p in t["series"]}
            if yr not in pts or not pts[yr].get("alive", True):
                continue
            p = pts[yr]
            base = v_dh(t["D"], t["H"])
            scale = (V_all[i] / base) if base > 0 else 1.0
            vol += float(v_dh(p["dbh_cm"], p["height_m"])) * scale
        traj.append({"jahr": yr, "CO2_t_ha": vol * RHO * BEF * (1 + RS) * CF * C2CO2 / area})
    sink = (traj[-1]["CO2_t_ha"] - traj[0]["CO2_t_ha"]) / (traj[-1]["jahr"] - traj[0]["jahr"]) if len(traj) > 1 else None

    out = {
        "bestand": {"flaeche_ha": area, "baeume": len(trees), "QSM_stamm_plausibel": int(has_q.sum()), "kalibrierung_n": int(cal.sum()),
                    "grundflaeche_m2_ha": float((np.pi / 4 * (D / 100) ** 2).sum() / area), "stammvolumen_m3_ha": float(V_all.sum() / area)},
        "annahmen": {"raumdichte_t_m3": [RHO_LO, RHO, RHO_HI], "ast_expansion": [BEF_LO, BEF, BEF_HI], "C_anteil": CF, "wurzel_spross": [RS_LO, RS, RS_HI]},
        "befund_qsm_kronenholz": {"median_QSM_gesamtholz_zu_stamm": qsm_wood_ratio, "plausibel_fuer_buche": "ca. 1,15-1,40"},
        "qsm_weg": res_qsm,
        "qsm_weg_CO2_spanne_t_ha": [lo, hi],
        "jenkins_2003": res_jenkins,
        "verhaeltnis_qsm_zu_jenkins_AGB": res_qsm["AGB_t_ha"] / res_jenkins["AGB_t_ha"],
        "modell_DH_nls": {"a": float(np.exp(th_dh[0])), "b_D": float(th_dh[1]), "c_H": float(th_dh[2]), "delta_varianz": delta_dh},
        "modell_ALS_nls": {"a": float(np.exp(m_als["nls"][0][0])), "b_HxCD": float(m_als["nls"][0][1]), "delta_varianz": m_als["nls"][1]},
        "loo_rel_rmse_bias_pct": {k: [round(v[0], 1), round(v[1], 1)] for k, v in q.items()},
        "trajektorie": traj,
        "senke_t_CO2_ha_jahr": sink,
        "senke_wert_eur_ha_jahr_uba2026": sink * UBA_EUR_T if sink else None,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
