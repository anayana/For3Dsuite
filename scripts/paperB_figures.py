#!/usr/bin/env python3
"""paperB_figures.py -- Abbildungen fuer Paper B aus results/geometry_per_class.csv.

Fig. 1: Vollstaendigkeit bei 10 cm je Bauteilklasse und Gebaeude (Balken).
Fig. 2: Median-Abstand je Klasse (log-Achse; Floater-dominierte Werte markiert).

  python scripts/paperB_figures.py [--out Paper_ODT/Heritage_Toolkit_Paper/figures]
"""
import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
P = REPO / "Paper_ODT" / "Heritage_Toolkit_Paper"
CLASSES = ["arch", "column", "moulding", "floor", "door/\nwindow", "wall", "stair", "vault", "roof", "other"]
BUILDINGS = ["5_CB", "3_SS", "2_OSA"]
COLORS = ["#1b6ca8", "#e08a1e", "#3a9e5f"]


def load(path):
    t = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            t[(r["building"], r["label"])] = r
    return t


def bars(t, key, ylabel, out, log=False, flag=None):
    x = np.arange(len(CLASSES))
    w = 0.27
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for i, (b, c) in enumerate(zip(BUILDINGS, COLORS)):
        vals = [float(t[(b, str(k))][key]) if (b, str(k)) in t else np.nan for k in range(10)]
        ax.bar(x + (i - 1) * w, vals, w, label=f"{b} (all: {float(t[(b, 'all')][key]):g})", color=c)
        if flag:
            for k, v in enumerate(vals):
                if not np.isnan(v) and v > flag:
                    ax.text(x[k] + (i - 1) * w, v, "*", ha="center", va="bottom", fontsize=11)
    ax.set_xticks(x, CLASSES, fontsize=8)
    ax.set_ylabel(ylabel)
    if log:
        ax.set_yscale("log")
    ax.legend(fontsize=8, frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, 1.0))
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print("->", out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=str(P / "figures"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t = load(P / "results" / "geometry_per_class.csv")
    bars(t, "compl_10cm", "Completeness at 10 cm", out / "fig1_completeness_10cm.png")
    bars(t, "median_cm", "Median distance [cm] (log)", out / "fig2_median.png", log=True, flag=50)


if __name__ == "__main__":
    main()
