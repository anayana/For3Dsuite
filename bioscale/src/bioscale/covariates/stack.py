"""Stapel der Basis-Layer auf dem Analyseraster; mehrskalige Merkmale werden bei Bedarf berechnet."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..grid import Grid, read_to_grid, write_raster
from ..multiscale import focal_mean
from ..provenance import LayerRecord, Provenance, file_checksum


@dataclass
class Layer:
    name: str
    array: np.ndarray
    group: str = "other"
    kind: str = "continuous"   # continuous | binary | categorical
    multiscale: bool = True     # False: nur am Punkt (z. B. Klima, das schon grossraeumig ist)


@dataclass
class CovariateStack:
    grid: Grid
    layers: dict = field(default_factory=dict)
    provenance: Provenance = field(default_factory=Provenance)
    kernel: str = "gauss"
    _cache: dict = field(default_factory=dict, repr=False)

    def add(self, layer: Layer, record: LayerRecord | None = None):
        if layer.kind == "categorical":
            # in Klassen-Indikatoren zerlegen -> Anteile im Wirkradius
            vals = np.unique(layer.array[np.isfinite(layer.array)])
            for v in vals:
                ind = np.where(np.isfinite(layer.array), (layer.array == v).astype("float32"), np.nan)
                if np.nanmean(ind) < 0.005:
                    continue
                nm = f"{layer.name}_{int(v)}"
                self.layers[nm] = Layer(nm, ind, layer.group, "binary", layer.multiscale)
                if record:
                    r = LayerRecord(**{**record.__dict__, "name": nm, "kind": "binary"})
                    r.processing = record.processing + [f"Indikator Klasse {int(v)}"]
                    self.provenance.add(r)
            return
        self.layers[layer.name] = layer
        if record:
            record.kind = layer.kind
            self.provenance.add(record)

    def add_file(self, path, name, group="other", kind="continuous", source="Nutzerdatei", license="", band=1):
        resampling = "nearest" if kind in ("categorical", "binary") else "bilinear"
        arr = read_to_grid(path, self.grid, band=band, resampling=resampling)
        rec = LayerRecord(name=name, source=source, group=group, origin=str(path), license=license,
                          processing=[f"auf Analyseraster {self.grid.res:g} m ({self.grid.crs}) gebracht, {resampling}"],
                          checksum=file_checksum(path))
        self.add(Layer(name, arr, group, kind), rec)

    def feature(self, base: str, radius: float) -> np.ndarray:
        key = (base, float(radius))
        if key not in self._cache:
            L = self.layers[base]
            self._cache[key] = (L.array if (radius <= 0 or not L.multiscale)
                                else focal_mean(L.array, radius, self.grid.res, self.kernel).astype("float32"))
        return self._cache[key]

    def sample_features(self, bases_radii: dict, x, y, keep=()):
        """{(base, r): Werte an Punkten}. Nur Merkmale in `keep` bleiben im Speicher."""
        out = {}
        for b, radii in bases_radii.items():
            for r in radii:
                key = (b, float(r))
                arr = self.feature(b, r)
                out[key] = self.grid.sample(arr, x, y)
                if key not in keep:
                    self._cache.pop(key, None)
        return out

    def matrix(self, chosen, mask):
        return np.column_stack([self.feature(b, r)[mask] for b, r in chosen])

    def save_layers(self, folder, chosen):
        folder = Path(folder)
        for b, r in chosen:
            write_raster(folder / f"{b}@{int(r)}m.tif", self.feature(b, r), self.grid)
