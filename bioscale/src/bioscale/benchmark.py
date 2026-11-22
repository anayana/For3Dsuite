"""Schnittstelle fuer spaetere Pruefstaende (z. B. Biodiversitaets-Exploratorien, GeoPlant).

Die Daten selbst kommen NIE ins Repo. Ein Pruefstand ist ein lokaler Ordner mit:
  plots.csv        locationID, x, y (Projekt-KBS), region, habitat (wald|gruenland), optional LUI/ForMI
  responses.csv    locationID, response-Spalten (z. B. Artenzahl oder Vorkommen je Art)
  covariates/      GeoTIFFs (beliebig, werden wie Nutzerraster behandelt)
Die Schnittstelle erzeugt daraus je Zielgroesse eine Projektdatei und rechnet sie.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_benchmark(folder):
    folder = Path(folder)
    plots = pd.read_csv(folder / "plots.csv")
    resp = pd.read_csv(folder / "responses.csv")
    need = {"locationID", "x", "y"}
    if need - set(plots.columns):
        raise ValueError(f"plots.csv braucht Spalten {sorted(need)}")
    return plots.merge(resp, on="locationID"), sorted((folder / "covariates").glob("*.tif"))


def intensity_strata(plots: pd.DataFrame, col: str, n=3):
    """Intensitaetsklassen (z. B. LUI) fuer stratifizierte Auswertung: Wie gut funktioniert BioScale je Klasse?"""
    return pd.qcut(plots[col], n, labels=[f"{col}_niedrig", f"{col}_mittel", f"{col}_hoch"][:n])
