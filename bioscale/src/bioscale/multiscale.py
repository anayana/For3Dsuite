"""Mehrskalige Einflussgroessen: Kernel-Statistiken ueber eine Radienliste.

Konvention (ueberall in BioScale gleich): Der *Wirkradius* r ist 2 Sigma eines Gauss-Kernels.
Innerhalb von r liegen damit ca. 86 % des Gewichts (2D). Alternativ: Kreisscheibe ("disk"),
dann ist r der harte Radius (wie Puffer bei Jackson & Fahrig).

Raender und Luecken (NaN) werden durch normierte Faltung behandelt:
    f_r = K_r * (x * m) / K_r * m      (m = 1 wo Daten gueltig)
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage


def radius_to_sigma_px(radius_m: float, res: float) -> float:
    return max(radius_m / 2.0 / res, 1e-6)


def _disk(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    k = (x ** 2 + y ** 2 <= radius_px ** 2).astype(float)
    return k / k.sum()


def focal_mean(arr: np.ndarray, radius_m: float, res: float, kernel: str = "gauss") -> np.ndarray:
    """Distanzgewichtetes Mittel im Wirkradius (NaN-tolerant)."""
    a = np.asarray(arr, dtype="float64")
    m = np.isfinite(a).astype("float64")
    x = np.where(m > 0, a, 0.0)
    if radius_m <= res / 2:
        return np.where(m > 0, a, np.nan)
    if kernel == "gauss":
        s = radius_to_sigma_px(radius_m, res)
        num = ndimage.gaussian_filter(x, s, mode="constant", cval=0.0, truncate=3.0)
        den = ndimage.gaussian_filter(m, s, mode="constant", cval=0.0, truncate=3.0)
    elif kernel == "disk":
        k = _disk(radius_m / res)
        from scipy.signal import fftconvolve
        num = fftconvolve(x, k, mode="same")
        den = fftconvolve(m, k, mode="same")
    else:
        raise ValueError(f"Unbekannter Kernel: {kernel}")
    with np.errstate(invalid="ignore", divide="ignore"):
        out = num / den
    out[den < 1e-3] = np.nan
    return out


def focal_sd(arr, radius_m, res, kernel="gauss"):
    """Heterogenitaet im Wirkradius: gewichtete Standardabweichung."""
    mu = focal_mean(arr, radius_m, res, kernel)
    mu2 = focal_mean(np.asarray(arr, float) ** 2, radius_m, res, kernel)
    return np.sqrt(np.clip(mu2 - mu ** 2, 0, None))


def class_proportion(classes: np.ndarray, value, radius_m, res, kernel="gauss"):
    """Anteil einer Klasse (z. B. WorldCover 'Grasland') im Wirkradius."""
    c = np.asarray(classes, dtype="float64")
    vals = np.atleast_1d(value)
    ind = np.where(np.isfinite(c), np.isin(c, vals).astype(float), np.nan)
    return focal_mean(ind, radius_m, res, kernel)


def radius_list(rmin: float, rmax: float, n: int = 8, res: float | None = None) -> list[float]:
    """Logarithmisch gestufte Radien in der Profilspanne; nie kleiner als eine Zelle."""
    lo = max(rmin, res or 0.0)
    rs = np.geomspace(lo, max(rmax, lo * 1.0001), n)
    # auf "schoene" Werte runden
    nice = []
    for r in rs:
        mag = 10 ** np.floor(np.log10(r))
        v = round(r / mag * 2) / 2 * mag
        if not nice or v > nice[-1]:
            nice.append(float(v))
    return nice


def multiscale_stack(layers: dict, radii: list[float], res: float, kernel="gauss", stats=("mean",)):
    """Erzeugt {f"{name}@{r}m": array} fuer alle Layer und Radien.

    layers: {name: (array, kind)} mit kind in {continuous, binary, categorical}.
    Kategoriale Layer muessen vorher in Klassen-Indikatoren (binary) zerlegt werden.
    """
    out = {}
    for name, (arr, kind) in layers.items():
        for r in radii:
            out[f"{name}@{int(round(r))}m"] = focal_mean(arr, r, res, kernel)
            if "sd" in stats and kind == "continuous":
                out[f"{name}_sd@{int(round(r))}m"] = focal_sd(arr, r, res, kernel)
    return out


def split_feature(fname: str):
    """'chm@200m' -> ('chm', 200.0); ohne Radius -> (fname, 0.0)."""
    if "@" in fname and fname.endswith("m"):
        base, r = fname.rsplit("@", 1)
        try:
            return base, float(r[:-1])
        except ValueError:
            pass
    return fname, 0.0
