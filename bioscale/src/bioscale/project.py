"""Projektdatei (YAML): Gebiet, Zeitraum, Zielfrage, Profil, Datenquellen. Mit Assistent.

Minimalbeispiel:
    name: Buchenwald-Voegel
    area: gebiet.gpkg
    crs: EPSG:25832
    resolution_m: 20
    period: {start: 2025-04-01, end: 2025-07-31}
    question: {target: occurrence, species: Ficedula albicollis, profile: voegel_wald}
    occurrence: {path: punkte.csv, format: dwc}
    covariates:
      open: {sentinel2: true, dem: true, worldcover: true}
      local: [{path: chm.tif, name: chm, group: structure}]
      als: {paths: [kachel1.laz]}
    output: ergebnis
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

DEFAULTS = {
    "resolution_m": 20,
    "crs": "EPSG:25832",
    "period": {"start": None, "end": None},
    "question": {"target": "occurrence", "species": "", "profile": "voegel_wald", "profile_overrides": {}},
    "occurrence": {"format": "dwc", "type": "auto", "complete_lists": True},
    "covariates": {"local": [], "open": {}, "als": None, "access": None, "kernel": "gauss"},
    "model": {"candidates": ["glm", "rf"], "cv": "knndm", "folds": 5, "bootstrap": 20, "seed": 0,
              "corr_max": 0.7, "events_per_variable": 10},
    "sampling": {"n_suggestions": 10, "min_distance_m": None},
    "sensitive": {"taxa": [], "coarsen_m": 1000, "publish_resolution_m": 250},
    "output": "ergebnis",
}

TARGETS = {
    "occurrence": "Vorkommen einer Art (Wahrscheinlichkeit)",
    "abundance": "Haeufigkeit/Aktivitaet einer Art (Zaehlungen)",
    "richness": "Artenzahl je Standort (vollstaendige Artenlisten, rarefiziert)",
}


def _deep_update(base, new):
    for k, v in (new or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def load_project(path) -> dict:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cfg = _deep_update(copy.deepcopy(DEFAULTS), raw)
    cfg["_base"] = str(path.parent.resolve())
    cfg["_file"] = str(path.resolve())
    validate_project(cfg)
    return cfg


def validate_project(cfg: dict):
    errs = []
    base = Path(cfg.get("_base", "."))
    if not cfg.get("area"):
        errs.append("'area' fehlt (GeoPackage/GeoJSON des Untersuchungsgebiets).")
    elif not (base / cfg["area"]).exists():
        errs.append(f"Gebietsdatei nicht gefunden: {cfg['area']}")
    occ = cfg.get("occurrence") or {}
    if not occ.get("path"):
        errs.append("'occurrence.path' fehlt (Punktdaten).")
    elif not any((base).glob(occ["path"])) and not (base / occ["path"]).exists():
        errs.append(f"Punktdaten nicht gefunden: {occ['path']}")
    if not cfg["question"].get("species") and cfg["question"].get("target") != "richness":
        errs.append("'question.species' fehlt (wissenschaftlicher Artname).")
    if float(cfg["resolution_m"]) < 1:
        errs.append("'resolution_m' muss >= 1 sein.")
    if cfg["question"].get("target") not in TARGETS:
        errs.append(f"'question.target' muss eines von {list(TARGETS)} sein.")
    for L in cfg["covariates"].get("local") or []:
        if not (base / L["path"]).exists():
            errs.append(f"Raster nicht gefunden: {L['path']}")
    if errs:
        raise ValueError("Projektdatei fehlerhaft:\n  - " + "\n  - ".join(errs))


def save_project(cfg: dict, path):
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    Path(path).write_text(yaml.safe_dump(clean, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def make_project(area, points, species, profile, out="ergebnis", fmt="dwc", resolution_m=20, crs="EPSG:25832",
                 start=None, end=None, rasters=None, open_data=None, als=None, name=None):
    cfg = {
        "name": name or f"{species} ({profile})",
        "area": str(area), "crs": crs, "resolution_m": resolution_m,
        "period": {"start": start, "end": end},
        "question": {"target": "occurrence", "species": species, "profile": profile},
        "occurrence": {"path": str(points), "format": fmt, "type": "auto"},
        "covariates": {"local": rasters or [], "open": open_data or {}, "als": als},
        "output": out,
    }
    return cfg


def wizard(path="projekt.yml", ask=input, say=print):
    """Fragt Schritt fuer Schritt ab und schreibt die Projektdatei."""
    from .profiles import list_profiles, load_profile
    say("BioScale-Assistent - Enter uebernimmt den Vorschlag in [Klammern].")

    def q(text, default=""):
        a = ask(f"{text} [{default}]: ").strip()
        return a or default

    name = q("Projektname", "Mein Projekt")
    area = q("Gebietsdatei (GeoPackage/GeoJSON)", "gebiet.gpkg")
    crs = q("Koordinatensystem (metrisch)", "EPSG:25832")
    points = q("Punktdaten (Darwin-Core-CSV, Camtrap-DP-Ordner, BirdNET/BatDetect2-CSV)", "punkte.csv")
    fmt = q("Format: dwc | camtrapdp | birdnet | batdetect2", "dwc")
    species = q("Zielart (wissenschaftlicher Name)", "")
    say("Profile: " + ", ".join(f"{p} ({load_profile(p)['label']})" for p in list_profiles()))
    profile = q("Profil", "voegel_wald")
    res = float(q("Rasterweite in m (10-25 empfohlen)", "20"))
    start = q("Zeitraum Beginn (JJJJ-MM-TT)", "")
    end = q("Zeitraum Ende (JJJJ-MM-TT)", "")
    s2 = q("Sentinel-2 laden? (j/n)", "j").lower().startswith("j")
    dem = q("Hoehenmodell (Copernicus DEM) laden? (j/n)", "j").lower().startswith("j")
    wc = q("Landbedeckung (ESA WorldCover) laden? (j/n)", "j").lower().startswith("j")
    rasters = []
    while True:
        r = q("Eigenes Raster hinzufuegen (Pfad, leer = fertig)", "")
        if not r:
            break
        rasters.append({"path": r, "name": Path(r).stem, "group": q("  Gruppe (structure/spectral/topography/landcover/intensity/climate)", "structure")})
    las = q("ALS-Punktwolke (LAZ, leer = keine)", "")
    cfg = make_project(area, points, species, profile, fmt=fmt, resolution_m=res, crs=crs, start=start or None,
                       end=end or None, rasters=rasters, name=name,
                       open_data={"sentinel2": s2, "dem": dem, "worldcover": wc},
                       als={"paths": [las]} if las else None)
    if fmt in ("birdnet", "batdetect2"):
        cfg["occurrence"]["sites"] = q("Standorttabelle (CSV: locationID, latitude, longitude)", "standorte.csv")
    save_project(cfg, path)
    say(f"Gespeichert: {path}. Starten mit:  bioscale run {path}")
    return path
