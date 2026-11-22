"""Profil-Bibliothek je Artengruppe: Variablengruppen, Wirkradius-Spanne, empfohlenes Modell, Hinweise.

Startwerte sind EXPERTENSCHAETZUNGEN und muessen geprueft werden (Feld `status`).
Eigene Profile: YAML-Datei mit gleichem Aufbau, im Projekt unter question.profile als Pfad angeben.
"""
from __future__ import annotations

from pathlib import Path

import yaml

HERE = Path(__file__).parent
REQUIRED = {"name", "label", "radius_m", "variable_groups", "recommended_model", "status"}


def list_profiles():
    return sorted(p.stem for p in HERE.glob("*.yml"))


def load_profile(name_or_path) -> dict:
    p = Path(str(name_or_path))
    if not p.suffix:
        p = HERE / f"{name_or_path}.yml"
    if not p.exists():
        raise FileNotFoundError(f"Profil '{name_or_path}' nicht gefunden. Vorhanden: {', '.join(list_profiles())}")
    prof = yaml.safe_load(p.read_text(encoding="utf-8"))
    missing = REQUIRED - set(prof)
    if missing:
        raise ValueError(f"Profil {p.name}: Felder fehlen: {sorted(missing)}")
    lo, hi = prof["radius_m"]
    if not (0 < lo < hi):
        raise ValueError(f"Profil {p.name}: radius_m muss [min, max] mit 0 < min < max sein")
    prof.setdefault("n_radii", 8)
    prof.setdefault("hints", [])
    prof.setdefault("references", [])
    prof.setdefault("domain", "wald")
    return prof


def merge_overrides(prof: dict, overrides: dict | None) -> dict:
    """Nutzer passt Profil im Projekt an (z. B. andere Radienspanne)."""
    if not overrides:
        return prof
    out = dict(prof)
    out.update(overrides)
    out["status"] = prof["status"] + " | im Projekt angepasst"
    return out
