"""Virtuelle Art in virtueller Landschaft - der Nachweis der Kernidee.

Die "Wahrheit" ist bekannt:
  * Wirkradius der Waldbindung (Standard 200 m, Gauss-Kernel, r = 2 Sigma),
  * Hoehenbezug (Art meidet Hochlagen),
  * ein unbeobachtetes raeumliches Feld (raeumlich autokorrelierte Residuen).
Die Stichprobe ist verzerrt: Standorte an Wegen, in Gruppen, nur im Westteil.
Damit muss die Pipeline (a) den Radius wiederfinden, (b) den Ostteil als Extrapolation
markieren und (c) raeumliche Kreuzvalidierung pessimistischer zeigen als zufaellige.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from .grid import Grid, write_raster
from .multiscale import focal_mean

DEMO_CRS = "EPSG:25832"
DEMO_ORIGIN = (600000.0, 5655000.0)  # beliebige Lage in Mitteleuropa, UTM 32N


def _field(rng, shape, sigma_px):
    f = ndimage.gaussian_filter(rng.standard_normal(shape), sigma_px, mode="reflect")
    return (f - f.mean()) / f.std()


def _z(a):
    return (a - np.nanmean(a)) / np.nanstd(a)


@dataclass
class VirtualWorld:
    grid: Grid
    layers: dict            # name -> array (Beobachtbare Einflussgroessen)
    kinds: dict             # name -> continuous | binary
    psi: np.ndarray         # wahre Vorkommenswahrscheinlichkeit
    truth: dict             # Parameter der Wahrheit
    sites: pd.DataFrame     # Standorte mit Erhebungen
    roads: np.ndarray = field(repr=False, default=None)


def make_world(seed: int = 42, size_px: int = 300, res: float = 10.0, true_radius_m: float = 200.0,
               n_clusters: int = 60, per_cluster: int = 4, n_visits: int = 3, p_detect: float = 0.75,
               west_fraction: float = 0.5, latent_sd: float = 0.6, b_forest: float = 2.2, b_elev: float = -1.2) -> VirtualWorld:
    rng = np.random.default_rng(seed)
    grid = Grid(crs=DEMO_CRS, x0=DEMO_ORIGIN[0], y0=DEMO_ORIGIN[1], res=res, width=size_px, height=size_px)
    shape = grid.shape
    X, Y = grid.cell_centers()
    xn = (X - X.min()) / (X.max() - X.min())  # 0 = West, 1 = Ost

    # Wald: Mosaik aus grober und feiner Struktur
    f = 0.6 * _field(rng, shape, 12) + 0.4 * _field(rng, shape, 4)
    forest = (f > 0.1).astype("float32")
    canopy = np.where(forest > 0, 22 + 6 * _field(rng, shape, 3), 0.8 * np.abs(rng.standard_normal(shape))).astype("float32")
    canopy = np.clip(canopy, 0, 45)
    # Hoehe: Gradient West -> Ost plus Relief
    elev = (250 + 350 * xn + 25 * _field(rng, shape, 20)).astype("float32")
    ndvi = np.clip(0.5 + 0.15 * forest + 0.08 * _field(rng, shape, 8) + 0.05 * rng.standard_normal(shape) - 0.0002 * (elev - 250), -1, 1).astype("float32")

    # Wege: zwei horizontale, zwei vertikale Linien mit Knick
    roads = np.zeros(shape, bool)
    for r0 in (int(size_px * 0.3), int(size_px * 0.72)):
        rows = (r0 + 8 * np.sin(np.arange(size_px) / 25)).astype(int)
        roads[np.clip(rows, 0, size_px - 1), np.arange(size_px)] = True
    for c0 in (int(size_px * 0.18), int(size_px * 0.4), int(size_px * 0.8)):
        cols = (c0 + 6 * np.cos(np.arange(size_px) / 30)).astype(int)
        roads[np.arange(size_px), np.clip(cols, 0, size_px - 1)] = True
    dist_road = (ndimage.distance_transform_edt(~roads) * res).astype("float32")

    # Wahrheit
    forest_r = focal_mean(forest, true_radius_m, res)
    latent = _field(rng, shape, 25)
    b0 = -0.3
    eta = b0 + b_forest * _z(forest_r) + b_elev * _z(elev) + latent_sd * latent
    psi = 1 / (1 + np.exp(-eta))

    # Verzerrte Stichprobe: Gruppen an Wegen, nur Westteil
    cand = np.argwhere((dist_road < 60) & (xn < west_fraction) & (xn > 0.03) & (Y > Y.min() + 50) & (Y < Y.max() - 50))
    centers = cand[rng.choice(len(cand), n_clusters, replace=False)]
    rows, cols, cl = [], [], []
    for k, (r, c) in enumerate(centers):
        for _ in range(per_cluster):
            rr = int(np.clip(r + rng.normal(0, 6), 0, size_px - 1))
            cc = int(np.clip(c + rng.normal(0, 6), 0, size_px - 1))
            rows.append(rr); cols.append(cc); cl.append(k)
    rows, cols = np.array(rows), np.array(cols)
    x = X[rows, cols] + rng.uniform(-res / 2, res / 2, len(rows))
    y = Y[rows, cols] + rng.uniform(-res / 2, res / 2, len(rows))
    z = rng.random(len(rows)) < psi[rows, cols]
    det = (rng.random((len(rows), n_visits)) < p_detect) & z[:, None]
    sites = pd.DataFrame(dict(locationID=[f"S{i:03d}" for i in range(len(rows))], x=x, y=y, cluster=cl,
                              occupied_true=z.astype(int)))
    for v in range(n_visits):
        sites[f"visit{v + 1}"] = det[:, v].astype(int)

    layers = dict(forest=forest, canopy_height=canopy, elevation=elev, ndvi=ndvi, dist_road=dist_road)
    kinds = dict(forest="binary", canopy_height="continuous", elevation="continuous", ndvi="continuous",
                 dist_road="continuous")
    truth = dict(true_radius_m=true_radius_m, b0=b0, b_forest=b_forest, b_elev=b_elev, latent_sd=latent_sd,
                 p_detect=p_detect, n_visits=n_visits, west_fraction=west_fraction, kernel="gauss (r = 2 sigma)")
    return VirtualWorld(grid=grid, layers=layers, kinds=kinds, psi=psi, truth=truth, sites=sites, roads=roads)


def to_dwc(world: VirtualWorld, species="Virtualis exemplaris", start="2025-05-01") -> pd.DataFrame:
    """Erhebungen als Darwin-Core-Tabelle (eine Zeile je Begehung, mit Fehlen)."""
    from pyproj import Transformer
    tr = Transformer.from_crs(world.grid.crs, "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(world.sites.x.values, world.sites.y.values)
    rows = []
    vcols = [c for c in world.sites.columns if c.startswith("visit")]
    base = pd.Timestamp(start)
    for i, s in world.sites.iterrows():
        for k, vc in enumerate(vcols):
            rows.append(dict(
                occurrenceID=f"{s.locationID}-{k + 1}", eventID=f"{s.locationID}-V{k + 1}", locationID=s.locationID,
                scientificName=species, occurrenceStatus="present" if s[vc] else "absent",
                individualCount=int(s[vc]), decimalLongitude=round(lon[i], 7), decimalLatitude=round(lat[i], 7),
                coordinateUncertaintyInMeters=10, eventDate=(base + pd.Timedelta(days=21 * k)).date().isoformat(),
                samplingProtocol="Punkt-Stopp 10 min", samplingEffort="10 min", basisOfRecord="HumanObservation"))
    return pd.DataFrame(rows)


def make_community(world: VirtualWorld, n_species: int = 25, p_detect: float = 0.7, seed: int = 7):
    """Virtuelle Artengemeinschaft auf den Standorten der virtuellen Welt.

    Jede Art reagiert mit eigenem Wirkradius (50-400 m) und eigener Staerke auf Wald und Hoehe.
    Wahrheit: erwartete Artenzahl je Zelle = Summe der psi_s (perfekter Nachweis).
    Rueckgabe: DwC-Tabelle (vollstaendige Listen, 3 Begehungen), Wahrheitskarte, Artenparameter.
    """
    from pyproj import Transformer
    rng = np.random.default_rng(seed)
    g = world.grid
    elev = world.layers["elevation"]
    truth = np.zeros(g.shape)
    s = world.sites
    n_vis = len([c for c in s.columns if c.startswith("visit")])
    tr = Transformer.from_crs(g.crs, "EPSG:4326", always_xy=True)
    lon, lat = tr.transform(s.x.values, s.y.values)
    rows, params = [], []
    for k in range(n_species):
        r = float(rng.choice([50, 100, 200, 400]))
        bf = rng.normal(1.0, 1.0)      # die meisten Arten mogen Wald, einige meiden ihn
        be = rng.normal(-0.5, 0.6)
        b0 = rng.normal(-0.8, 0.8)
        psi = 1 / (1 + np.exp(-(b0 + bf * _z(focal_mean(world.layers["forest"], r, g.res)) + be * _z(elev))))
        truth += psi
        z = rng.random(len(s)) < g.sample(psi, s.x.values, s.y.values)
        det = (rng.random((len(s), n_vis)) < p_detect) & z[:, None]
        name = f"Virtualis species{k + 1:02d}"
        params.append(dict(name=name, radius=r, b_forest=bf, b_elev=be, b0=b0))
        for i in np.flatnonzero(z):
            for v in np.flatnonzero(det[i]):
                rows.append(dict(scientificName=name, occurrenceStatus="present", locationID=s.locationID.iloc[i],
                                 eventID=f"{s.locationID.iloc[i]}-V{v + 1}", decimalLongitude=round(lon[i], 7),
                                 decimalLatitude=round(lat[i], 7), eventDate=f"2025-0{5 + v}-10",
                                 basisOfRecord="HumanObservation", samplingProtocol="vollstaendige Artenliste"))
    # Begehungen ohne Nachweis als leere Liste dokumentieren (damit die Begehungszahl stimmt)
    seen = {(r_["locationID"], r_["eventID"]) for r_ in rows}
    for i, loc in enumerate(s.locationID):
        for v in range(n_vis):
            if (loc, f"{loc}-V{v + 1}") not in seen:
                rows.append(dict(scientificName="", occurrenceStatus="absent", locationID=loc, eventID=f"{loc}-V{v + 1}",
                                 decimalLongitude=round(lon[i], 7), decimalLatitude=round(lat[i], 7),
                                 eventDate=f"2025-0{5 + v}-10", basisOfRecord="HumanObservation",
                                 samplingProtocol="vollstaendige Artenliste (keine Art)"))
    return pd.DataFrame(rows), truth.astype("float32"), params


def write_demo_project(outdir, seed: int = 42, **kw) -> Path:
    """Schreibt ein vollstaendiges Beispielprojekt (Raster, Punkte, Gebiet, projekt.yml)."""
    import yaml
    out = Path(outdir)
    (out / "daten").mkdir(parents=True, exist_ok=True)
    w = make_world(seed=seed, **kw)
    for name, arr in w.layers.items():
        write_raster(out / "daten" / f"{name}.tif", arr, w.grid)
    write_raster(out / "daten" / "wahrheit_psi.tif", w.psi, w.grid)
    to_dwc(w).to_csv(out / "daten" / "erhebungen_dwc.csv", index=False)
    minx, miny, maxx, maxy = w.grid.bounds
    area = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25832"}},
            "features": [{"type": "Feature", "properties": {"name": "Virtuelles Schutzgebiet"},
                          "geometry": {"type": "Polygon", "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy],
                                                                           [minx, maxy], [minx, miny]]]}}]}
    (out / "daten" / "gebiet.geojson").write_text(json.dumps(area), encoding="utf-8")
    (out / "daten" / "wahrheit_psi.json").write_text(json.dumps(w.truth, indent=2), encoding="utf-8")
    groups = dict(forest="landcover", canopy_height="structure", elevation="topography", ndvi="spectral",
                  dist_road="access")
    proj = {
        "name": "Demo: virtuelle Art im virtuellen Schutzgebiet",
        "area": "daten/gebiet.geojson",
        "crs": DEMO_CRS,
        "resolution_m": w.grid.res,
        "period": {"start": "2025-05-01", "end": "2025-07-31"},
        "question": {"target": "occurrence", "species": "Virtualis exemplaris", "profile": "demo_virtuelle_art"},
        "occurrence": {"path": "daten/erhebungen_dwc.csv", "format": "dwc", "type": "auto"},
        "covariates": {"local": [
            {"path": f"daten/{n}.tif", "name": n, "group": groups[n], "kind": w.kinds[n]}
            for n in w.layers if n != "dist_road"],
            "access": {"path": "daten/dist_road.tif", "name": "dist_road"}},
        "model": {"candidates": ["glm", "rf"], "cv": "knndm", "folds": 5, "bootstrap": 20, "seed": seed},
        "sampling": {"n_suggestions": 12},
        "output": "ergebnis",
        "demo_truth": "daten/wahrheit_psi.tif",
    }
    (out / "projekt.yml").write_text(yaml.safe_dump(proj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    # Zweites Projekt: Artenzahl einer virtuellen Gemeinschaft
    com, truth_s, params = make_community(w, seed=seed + 1)
    com.to_csv(out / "daten" / "artenlisten_dwc.csv", index=False)
    write_raster(out / "daten" / "wahrheit_artenzahl.tif", truth_s, w.grid)
    (out / "daten" / "wahrheit_artenzahl.json").write_text(json.dumps({"arten": params}, indent=1), encoding="utf-8")
    rich = dict(proj, name="Demo: Artenzahl einer virtuellen Gemeinschaft",
                question={"target": "richness", "species": "", "profile": "demo_virtuelle_art"},
                occurrence={"path": "daten/artenlisten_dwc.csv", "format": "dwc"},
                output="ergebnis_artenzahl", demo_truth="daten/wahrheit_artenzahl.tif")
    rich["model"] = dict(proj["model"], candidates=["glm", "rf"])
    (out / "projekt_artenzahl.yml").write_text(yaml.safe_dump(rich, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return out / "projekt.yml"
