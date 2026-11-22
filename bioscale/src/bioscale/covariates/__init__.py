"""Einflussgroessen: offene Daten (Sentinel-1/-2, Copernicus DEM, WorldCover, HRL, DWD) und Nutzerdaten
(ALS, Drohne, eigene Raster). Alles landet auf dem gemeinsamen Analyseraster, mit Provenienz je Layer."""
from .stack import CovariateStack, Layer  # noqa: F401
