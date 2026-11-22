"""Intensitaet statt Klasse: kontinuierliche Nutzungs- und Stoerungsgroessen aus Zeitreihen.

* Mahd-/Ernteereignisse: abrupter NDVI-Abfall mit anschliessendem Wiederanstieg (Gruenland).
* Saisonale Amplitude und Vegetationsdauer (Offenland, Acker).
* Stoerung im Wald: Abfall des NDMI/NBR gegenueber dem Vorjahresmedian.
Alle Funktionen arbeiten auf Wuerfeln (Zeit x Zeile x Spalte) mit NaN fuer Wolken.
Einfache, nachvollziehbare Regeln (MVP). Phase 2: Abgleich mit Referenz-Mahdterminen.
"""
from __future__ import annotations

import warnings

import numpy as np


def _interp_time(cube):
    """Luecken (NaN) je Pixel linear ueber die Zeit fuellen (Raender: naechster Wert)."""
    T = cube.shape[0]
    flat = cube.reshape(T, -1).copy()
    t = np.arange(T)
    for j in np.flatnonzero(np.isfinite(flat).sum(0) >= 2):
        v = flat[:, j]
        ok = np.isfinite(v)
        if not ok.all():
            flat[:, j] = np.interp(t, t[ok], v[ok])
    return flat.reshape(cube.shape)


def mowing_events(dates, ndvi_cube, drop=0.15, regrow=0.08, max_gap_days=40):
    """Zaehlt Mahd-/Ernteereignisse je Pixel.

    Ereignis = NDVI faellt zwischen zwei gueltigen Aufnahmen (<= max_gap_days) um >= drop
    und steigt danach wieder um >= regrow (unterscheidet Mahd von Seneszenz).
    """
    days = np.array([(d - dates[0]).days for d in dates])
    cube = np.asarray(ndvi_cube, float)
    T = cube.shape[0]
    flat = cube.reshape(T, -1)
    out = np.zeros(flat.shape[1])
    valid_any = np.isfinite(flat).sum(0) >= 3
    for j in np.flatnonzero(valid_any):
        v = flat[:, j]
        idx = np.flatnonzero(np.isfinite(v))
        x, d = v[idx], days[idx]
        k, n = 0, 0
        while k < len(x) - 1:
            if x[k] - x[k + 1] >= drop and d[k + 1] - d[k] <= max_gap_days:
                low = x[k + 1]
                after = x[k + 2:]
                if len(after) and np.nanmax(after[:4]) - low >= regrow:
                    n += 1
                    k += 2
                    continue
            k += 1
        out[j] = n
    out[~valid_any] = np.nan
    return out.reshape(cube.shape[1:]).astype("float32")


def seasonal_amplitude(ndvi_cube):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return (np.nanpercentile(ndvi_cube, 90, 0) - np.nanpercentile(ndvi_cube, 10, 0)).astype("float32")


def disturbance(dates, cube, ref_year, year, threshold=0.1):
    """Abfall des Jahresmedians (z. B. NDMI) von ref_year zu year. Positiv = Verlust."""
    y = np.array([d.year for d in dates])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        a = np.nanmedian(cube[y == ref_year], 0)
        b = np.nanmedian(cube[y == year], 0)
    loss = (a - b).astype("float32")
    return loss, (loss >= threshold).astype("float32")


def intensity_layers(series: dict):
    """Aus Sentinel-2-Zeitreihen die Standard-Intensitaetsgroessen ableiten."""
    out = {}
    if "NDVI" in series:
        dates, cube = series["NDVI"]
        if len(dates) >= 4:
            out["int_mahd_ereignisse"] = mowing_events(dates, cube)
            out["int_ndvi_amplitude"] = seasonal_amplitude(cube)
    if "NDMI" in series:
        dates, cube = series["NDMI"]
        ys = sorted({d.year for d in dates})
        if len(ys) >= 2:
            out[f"int_ndmi_verlust_{ys[0]}_{ys[-1]}"] = disturbance(dates, cube, ys[0], ys[-1])[0]
    return out
