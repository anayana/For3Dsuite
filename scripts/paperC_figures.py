#!/usr/bin/env python3
"""paperC_figures.py -- Abbildungen fuer Paper C aus den Ergebnistabellen.

  python scripts/paperC_figures.py   -> Paper_ODT/Forst_Benchmark_Paper/figures/fig*.png|pdf
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                            # noqa: E402
import numpy as np                                         # noqa: E402
import pandas as pd                                        # noqa: E402

REPO = Path(__file__).resolve().parents[1]
RES = REPO / "Paper_ODT" / "Forst_Benchmark_Paper" / "results"
FIG = REPO / "Paper_ODT" / "Forst_Benchmark_Paper" / "figures"

# Kategoriale Reihenfolge fest (validiert: CVD-Abstand ok; Kontrast-WARN -> Marker + Direktbeschriftung)
METHODS = ["kreisfit", "geofit", "ransac", "zylinder", "hough", "robust"]
LABEL = {"kreisfit": "Kasa circle", "geofit": "Geometric circle", "ransac": "RANSAC circle",
         "zylinder": "Cylinder", "hough": "Hough", "robust": "Huber-robust circle"}
COLOR = dict(zip(METHODS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6"]))
MARK = dict(zip(METHODS, ["o", "s", "^", "D", "v", "P"]))
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3de"

plt.rcParams.update({"font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": .6, "legend.frameon": False,
                     "savefig.dpi": 300, "font.family": "DejaVu Sans"})


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(FIG / f"{name}.{ext}", bbox_inches="tight")
    plt.close(fig)


def ref_lines(ax, thr=2.0, arc=202.5):
    ax.axhline(thr, color=INK, lw=.8, ls=(0, (4, 3)))
    ax.axvline(arc, color=MUTED, lw=.8, ls=":")


def fig_mc():
    d = pd.read_csv(RES / "arc_error_mc_real.csv")
    d = d[(d.n_pts == 200) & (d.dbh_cm == 40)]
    scen = [("ideal", "a  Ideal circle"), ("unrund", "b  Non-circular (axis ratio 0.85–1)"),
            ("ausr15", "c  15 % outliers"), ("komb", "d  Combined")]
    fig, axs = plt.subplots(2, 2, figsize=(7.2, 5.6), sharex=True, sharey=True)
    for ax, (s, title) in zip(axs.ravel(), scen):
        g = d[d.scenario == s]
        for m in METHODS:
            h = g[g.method == m].sort_values("arc_deg")
            ax.plot(h.arc_deg, h.rmse_cm, color=COLOR[m], lw=1.6, marker=MARK[m], ms=4, label=LABEL[m])
        ref_lines(ax)
        ax.set_title(title, loc="left", fontsize=9, color=INK)
        ax.set_yscale("log"); ax.set_ylim(.05, 60)
        ax.set_xticks([45, 90, 135, 180, 225, 270, 315, 360])
    for ax in axs[1]: ax.set_xlabel("Visible arc at breast height (°)")
    for ax in axs[:, 0]: ax.set_ylabel("RMSE of DBH (cm)")
    h, l = axs[0, 0].get_legend_handles_labels()
    fig.legend(h, l, ncol=3, fontsize=7.5, loc="lower center", bbox_to_anchor=(.5, -.04))
    fig.subplots_adjust(bottom=.16)
    fig.suptitle("Monte Carlo: DBH 40 cm, 200 points, σ = 5 mm (dashed: 2 cm; dotted: 202.5°)", x=.01, ha="left", fontsize=9, color=MUTED)
    save(fig, "fig1_mc_rmse_vs_arc")


def helios():
    ds = []
    for sc, lab in [("S1a", "400 ha⁻¹"), ("S1b", "800 ha⁻¹"), ("S1c", "1200 ha⁻¹")]:
        f = RES / f"helios_{sc}.csv"
        if f.exists():
            x = pd.read_csv(f); x["scene"] = lab; ds.append(x)
    return pd.concat(ds)


def fig_helios_error(d):
    for m in METHODS:
        d[m + "_err"] = d[m + "_cm"] - d.dbh_true_cm
    edges = [1, 90, 135, 180, 225, 270, 315, 361]
    mids = [45, 112.5, 157.5, 202.5, 247.5, 292.5, 338]
    d["cls"] = pd.cut(d.arc_geo_deg, edges, right=False)
    fig, axs = plt.subplots(1, 2, figsize=(7.2, 3.0))
    for m in METHODS:
        g = d.groupby("cls", observed=True)[m + "_err"]
        rmse = g.apply(lambda e: np.sqrt(np.nanmean(e ** 2))).values
        share = g.apply(lambda e: (e.abs() <= 2).sum() / max(len(e), 1)).values
        axs[0].plot(mids, rmse, color=COLOR[m], marker=MARK[m], ms=4, lw=1.6, label=LABEL[m])
        axs[1].plot(mids, 100 * share, color=COLOR[m], marker=MARK[m], ms=4, lw=1.6)
    ref_lines(axs[0]); axs[0].set_yscale("log"); axs[0].set_ylabel("RMSE of DBH (cm)")
    axs[1].axvline(202.5, color=MUTED, lw=.8, ls=":"); axs[1].set_ylabel("Stems with |error| ≤ 2 cm (%)"); axs[1].set_ylim(0, 100)
    for ax, t in zip(axs, ["a  Error by visible arc", "b  Share within 2 cm (incl. failures)"]):
        ax.set_xlabel("Geometrically visible arc (°)"); ax.set_xticks([0, 90, 180, 270, 360]); ax.set_title(t, loc="left", fontsize=9, color=INK)
    h, l = axs[0].get_legend_handles_labels()
    fig.legend(h, l, ncol=6, fontsize=7, loc="lower center", bbox_to_anchor=(.5, -.1))
    fig.suptitle(f"HELIOS++ scenes pooled (n = {len(d):,} stem × configuration cases)", x=.01, ha="left", fontsize=9, color=MUTED)
    save(fig, "fig2_helios_error_vs_arc")


def fig_design(d):
    scenes = list(dict.fromkeys(d.scene))
    lay = [("raster", "Grid", "#2a78d6", "o"), ("zufall", "Random (mean of 10)", "#eb6834", "s"), ("eng", "Clustered near centre", "#1baf7a", "^")]
    fig, axs = plt.subplots(1, len(scenes), figsize=(7.2, 2.7), sharey=True)
    for ax, sc in zip(np.atleast_1d(axs), scenes):
        g = d[d.scene == sc]
        for key, lab, col, mk in lay:
            h = g[g.layout == key].groupby("n_scans").arc_geo_deg.apply(lambda s: 100 * (s >= 180).mean())
            ax.plot(h.index, h.values, color=col, marker=mk, ms=4, lw=1.6, label=lab)
        ax.set_title(sc, loc="left", fontsize=9, color=INK); ax.set_xlabel("Scan positions"); ax.set_xticks([1, 2, 3, 4, 6, 9]); ax.set_ylim(0, 102)
    np.atleast_1d(axs)[0].set_ylabel("Stems with ≥ 180° visible (%)")
    np.atleast_1d(axs)[0].legend(fontsize=7, loc="lower right")
    save(fig, "fig3_design_coverage")


def fig_sector(d):
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    secs = sorted(d.arc_deg.unique())
    data = [d.loc[d.arc_deg == s, "arc_geo_deg"].values for s in secs]
    ax.boxplot(data, positions=secs, widths=14, showfliers=False, medianprops={"color": "#2a78d6", "lw": 1.6},
               boxprops={"color": MUTED}, whiskerprops={"color": MUTED}, capprops={"color": MUTED})
    ax.plot([0, 360], [0, 360], color=MUTED, lw=.8, ls=":")
    ax.axvline(202.5, color=INK, lw=.8, ls=(0, (4, 3))); ax.axhline(180, color=INK, lw=.8, ls=(0, (4, 3)))
    ax.set_xticks([0, 90, 180, 270, 360]); ax.set_xticklabels(["0", "90", "180", "270", "360"]); ax.set_xlim(-15, 375); ax.set_xlabel("Occupied sectors × 22.5° (3DFin rule)"); ax.set_ylabel("Geometrically visible arc (°)")
    save(fig, "fig4_sector_vs_geometric")


def main():
    fig_mc()
    d = helios()
    fig_helios_error(d.copy()); fig_design(d); fig_sector(d)
    print("->", FIG)


if __name__ == "__main__":
    main()
