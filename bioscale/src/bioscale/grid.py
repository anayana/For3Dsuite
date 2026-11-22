"""Gemeinsames Analyseraster und Raster-Ein/Ausgabe.

Alle Einflussgroessen werden auf EIN Raster gebracht (Standard 10-25 m, metrisches KBS).
Das Raster ist nordorientiert; Zeile 0 liegt oben (wie GeoTIFF).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.transform import from_origin, rowcol
from rasterio.warp import reproject


@dataclass(frozen=True)
class Grid:
    crs: str
    x0: float  # linke Kante
    y0: float  # obere Kante
    res: float
    width: int
    height: int

    @classmethod
    def from_bounds(cls, bounds, res: float, crs: str) -> "Grid":
        minx, miny, maxx, maxy = bounds
        x0 = np.floor(minx / res) * res
        y0 = np.ceil(maxy / res) * res
        width = int(np.ceil((maxx - x0) / res))
        height = int(np.ceil((y0 - miny) / res))
        return cls(crs=str(crs), x0=float(x0), y0=float(y0), res=float(res), width=width, height=height)

    @property
    def transform(self):
        return from_origin(self.x0, self.y0, self.res, self.res)

    @property
    def shape(self):
        return (self.height, self.width)

    @property
    def bounds(self):
        return (self.x0, self.y0 - self.height * self.res, self.x0 + self.width * self.res, self.y0)

    def cell_centers(self):
        xs = self.x0 + (np.arange(self.width) + 0.5) * self.res
        ys = self.y0 - (np.arange(self.height) + 0.5) * self.res
        return np.meshgrid(xs, ys)

    def rowcol(self, x, y):
        r, c = rowcol(self.transform, np.asarray(x), np.asarray(y))
        r, c = np.asarray(r), np.asarray(c)
        inside = (r >= 0) & (r < self.height) & (c >= 0) & (c < self.width)
        return r, c, inside

    def sample(self, arr: np.ndarray, x, y) -> np.ndarray:
        r, c, inside = self.rowcol(x, y)
        out = np.full(len(np.atleast_1d(r)), np.nan)
        out[inside] = arr[r[inside], c[inside]]
        return out

    def to_dict(self):
        return dict(crs=self.crs, x0=self.x0, y0=self.y0, res=self.res, width=self.width, height=self.height)


def write_raster(path, arr: np.ndarray, grid: Grid, nodata=np.nan, cog: bool = True, tags: dict | None = None):
    """Schreibt ein Band als (Cloud Optimized) GeoTIFF."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(arr)
    dtype = "float32" if arr.dtype.kind == "f" else arr.dtype.name
    profile = dict(driver="GTiff", height=grid.height, width=grid.width, count=1, dtype=dtype,
                   crs=grid.crs, transform=grid.transform, nodata=nodata, compress="deflate")
    if cog:
        try:
            # GDAL >= 3.1 hat den COG-Treiber
            profile["driver"] = "COG"
            with rasterio.open(path, "w", **profile) as dst:
                dst.write(arr.astype(dtype), 1)
                if tags:
                    dst.update_tags(**{k: str(v) for k, v in tags.items()})
            return path
        except Exception:
            profile["driver"] = "GTiff"
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(arr.astype(dtype), 1)
        if tags:
            dst.update_tags(**{k: str(v) for k, v in tags.items()})
    return path


def read_to_grid(path, grid: Grid, band: int = 1, resampling: str = "bilinear") -> np.ndarray:
    """Liest ein beliebiges Raster und bringt es (Reprojektion + Resampling) auf das Analyseraster."""
    out = np.full(grid.shape, np.nan, dtype="float32")
    rs = getattr(Resampling, resampling)
    with rasterio.open(path) as src:
        src_nodata = src.nodata
        reproject(
            source=rasterio.band(src, band),
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src_nodata,
            dst_transform=grid.transform,
            dst_crs=grid.crs,
            dst_nodata=np.nan,
            resampling=rs,
        )
    return out


def reproject_array(arr, src_transform, src_crs, grid: Grid, resampling="bilinear", src_nodata=None):
    out = np.full(grid.shape, np.nan, dtype="float32")
    reproject(source=np.asarray(arr, dtype="float32"), destination=out, src_transform=src_transform,
              src_crs=src_crs, src_nodata=src_nodata, dst_transform=grid.transform, dst_crs=grid.crs,
              dst_nodata=np.nan, resampling=getattr(Resampling, resampling))
    return out


def area_mask(grid: Grid, geometry) -> np.ndarray:
    """True innerhalb des Untersuchungsgebiets."""
    from rasterio.features import geometry_mask
    geoms = list(geometry) if hasattr(geometry, "__iter__") and not hasattr(geometry, "geom_type") else [geometry]
    return geometry_mask(geoms, out_shape=grid.shape, transform=grid.transform, invert=True, all_touched=True)


def aggregate(arr: np.ndarray, factor: int) -> np.ndarray:
    """Blockmittel (nan-tolerant), z. B. zum Vergroebern sensibler Ausgaben."""
    if factor <= 1:
        return arr
    h, w = arr.shape
    H, W = int(np.ceil(h / factor)) * factor, int(np.ceil(w / factor)) * factor
    pad = np.full((H, W), np.nan)
    pad[:h, :w] = arr
    blocks = pad.reshape(H // factor, factor, W // factor, factor)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            m = np.nanmean(blocks, axis=(1, 3))
    return np.repeat(np.repeat(m, factor, 0), factor, 1)[:h, :w]
