"""Halb-synthetisches Beispiel: ECHTE offene Daten, VIRTUELLE Art mit bekannter Wahrheit.

Aufruf:   python examples/echte_landschaft_virtuelle_art.py [zielordner]
Braucht Internet (S3-Buckets von ESA WorldCover und Copernicus DEM, Earth Search STAC + sentinel-cogs).

1. Laedt fuer 6 x 6 km im Spessart (Laubwald-Mittelgebirge) WorldCover und Copernicus DEM.
2. Definiert eine virtuelle Waldart: Baumanteil im Wirkradius 300 m (+), Hoehe (-).
3. Zieht verzerrte Standorte (nur Suedhaelfte) mit 3 Begehungen, schreibt Darwin Core.
4. Rechnet die normale Kette mit offenen Daten (Sentinel-2, DEM, WorldCover) und vergleicht mit der Wahrheit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from bioscale.covariates import opendata as OD
from bioscale.grid import Grid, write_raster
from bioscale.multiscale import focal_mean

X0, Y0, SIZE, RES = 530000, 5546000, 6000, 20.0
TRUE_RADIUS = 300.0


def main(out="echte_landschaft"):
    out = Path(out)
    (out / "daten").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(1)
    g = Grid("EPSG:25832", X0, Y0, RES, int(SIZE / RES), int(SIZE / RES))
    wc, _ = OD.worldcover(g)
    elev, _ = OD.copernicus_dem(g)
    trees = (wc == 10).astype(float)
    z = lambda a: (a - np.nanmean(a)) / np.nanstd(a)
    eta = 0.0 + 1.8 * z(focal_mean(trees, TRUE_RADIUS, RES)) - 0.8 * z(elev)
    psi = 1 / (1 + np.exp(-eta))
    write_raster(out / "daten" / "wahrheit_psi.tif", psi, g)
    (out / "daten" / "wahrheit.json").write_text(json.dumps({"true_radius_m": TRUE_RADIUS, "variable": "worldcover_10"}))
    X, Y = g.cell_centers()
    south = Y < Y0 - SIZE / 2
    cand = np.argwhere(south & np.isfinite(psi))
    pick = cand[rng.choice(len(cand), 200, replace=False)]
    from pyproj import Transformer
    tr = Transformer.from_crs(g.crs, "EPSG:4326", always_xy=True)
    rows = []
    for i, (r, c) in enumerate(pick):
        occ = rng.random() < psi[r, c]
        lon, lat = tr.transform(X[r, c], Y[r, c])
        for v in range(3):
            det = occ and rng.random() < 0.8
            rows.append(dict(scientificName="Virtualis silvatica", occurrenceStatus="present" if det else "absent",
                             decimalLongitude=lon, decimalLatitude=lat, locationID=f"P{i:03d}", eventID=f"P{i:03d}-{v}",
                             eventDate=f"2024-0{5 + v}-15", samplingEffort="10 min"))
    pd.DataFrame(rows).to_csv(out / "daten" / "erhebungen.csv", index=False)
    area = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25832"}},
            "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [[
                [X0, Y0 - SIZE], [X0 + SIZE, Y0 - SIZE], [X0 + SIZE, Y0], [X0, Y0], [X0, Y0 - SIZE]]]}}]}
    (out / "daten" / "gebiet.geojson").write_text(json.dumps(area))
    proj = {"name": "Echte Landschaft, virtuelle Art (Spessart)", "area": "daten/gebiet.geojson", "crs": "EPSG:25832",
            "resolution_m": RES, "period": {"start": "2024-04-01", "end": "2024-09-30"},
            "question": {"target": "occurrence", "species": "Virtualis silvatica", "profile": "voegel_wald"},
            "occurrence": {"path": "daten/erhebungen.csv", "format": "dwc"},
            "covariates": {"open": {"sentinel2": {"cloud_max": 40}, "dem": True, "worldcover": True}},
            "model": {"candidates": ["glm", "rf"], "bootstrap": 10}, "output": "ergebnis",
            "demo_truth": "daten/wahrheit_psi.tif"}
    p = out / "projekt.yml"
    p.write_text(yaml.safe_dump(proj, allow_unicode=True, sort_keys=False))
    from bioscale.pipeline import run
    res = run(p)
    print("Gewaehlt:", res["chosen"])
    print("Wahrheit:", res["truth"])
    print("Bericht:", res["report"])


if __name__ == "__main__":
    main(*sys.argv[1:])
