"""Punktdaten einlesen, Datentyp erkennen, Aufwand erfassen, pruefen, sensible Arten vergroebern.

Unterstuetzte Formate
  * Darwin Core (CSV oder GeoPackage): decimalLatitude/decimalLongitude, scientificName,
    occurrenceStatus, individualCount, eventDate, locationID, samplingEffort
  * Camtrap DP (datapackage.json + deployments.csv + observations.csv)
  * BirdNET-Analyzer-Tabellen (CSV, Spalten "Scientific name", "Confidence", "File")
  * BatDetect2-Tabellen (CSV, Spalten "class", "class_prob", "det_prob", Datei)
  BirdNET/BatDetect2 brauchen eine Standorttabelle (locationID, Koordinaten, optional effort).

Ergebnis ist immer eine Standorttabelle `Sites` (eine Zeile je Standort) mit
  locationID, x, y (Projekt-KBS), response, effort, n_visits, visit_1..visit_K (falls vorhanden).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

# Startliste sensibler Taxa (Gattung oder Art). Bewusst konservativ; im Projekt erweiterbar.
SENSITIVE_DEFAULT = [
    # Fledermaeuse (Quartiere)
    "Barbastella", "Eptesicus", "Myotis", "Nyctalus", "Pipistrellus", "Plecotus", "Rhinolophus", "Vespertilio",
    # Grossvoegel mit Horsten / stoerungsempfindlich
    "Aquila", "Haliaeetus albicilla", "Milvus", "Ciconia nigra", "Bubo bubo", "Falco peregrinus",
    "Pandion haliaetus", "Tetrao urogallus", "Lyrurus tetrix", "Strix uralensis",
    # Saeuger
    "Lynx lynx", "Felis silvestris", "Canis lupus",
    # Sammel-/Verfolgungsdruck
    "Cypripedium calceolus", "Rosalia alpina",
]

PRESENT = {"present", "presence", "1", "true", "ja", "yes", "detected", "vorhanden"}
ABSENT = {"absent", "absence", "0", "false", "nein", "no", "not detected", "fehlt"}


@dataclass
class Observations:
    sites: pd.DataFrame
    dtype: str                         # presence_absence | counts | presence_only
    species: str
    source_format: str
    crs: str
    background: pd.DataFrame | None = None   # Zielgruppen-Hintergrund (nur Vorkommen)
    issues: list[str] = field(default_factory=list)
    sensitive: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def n(self):
        return len(self.sites)

    @property
    def n_events(self):
        """Anzahl 'Ereignisse' fuer Faustregeln (seltenere Klasse bzw. Vorkommen)."""
        r = self.sites["response"].values
        if self.dtype == "presence_absence":
            return int(min((r > 0).sum(), (r == 0).sum()))
        if self.dtype == "counts":
            return int((r > 0).sum())
        return int(len(r))


# ---------------------------------------------------------------- Hilfen
def _to_project_xy(df, crs, lon="decimalLongitude", lat="decimalLatitude"):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    x, y = tr.transform(pd.to_numeric(df[lon], errors="coerce").values,
                        pd.to_numeric(df[lat], errors="coerce").values)
    return np.asarray(x), np.asarray(y)


def _status(v):
    s = str(v).strip().lower()
    if s in PRESENT:
        return 1
    if s in ABSENT:
        return 0
    return np.nan


def _effort_minutes(v):
    """'10 min', '2 h', '3 Naechte', '24' -> Zahl (Minuten bzw. Rohwert)."""
    if pd.isna(v):
        return np.nan
    s = str(v).lower().replace(",", ".")
    m = re.search(r"([\d.]+)", s)
    if not m:
        return np.nan
    x = float(m.group(1))
    if re.search(r"\bh\b|stunde|hour", s):
        return x * 60
    if re.search(r"tag|day|nacht|night", s):
        return x * 1440
    return x


def is_sensitive(name: str, extra: list[str] | None = None) -> bool:
    if not name:
        return False
    lst = SENSITIVE_DEFAULT + list(extra or [])
    n = name.strip().lower()
    return any(n == t.lower() or n.startswith(t.lower() + " ") for t in lst)


# ---------------------------------------------------------------- Leser
def read_table(path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() in (".gpkg", ".geojson", ".shp"):
        import geopandas as gpd
        g = gpd.read_file(p).to_crs("EPSG:4326")
        df = pd.DataFrame(g.drop(columns="geometry"))
        df["decimalLongitude"], df["decimalLatitude"] = g.geometry.x, g.geometry.y
        return df
    sep = "\t" if p.suffix.lower() in (".tsv", ".txt") else None
    return pd.read_csv(p, sep=sep, engine="python")


def sites_from_dwc(df: pd.DataFrame, species: str, crs: str, complete_lists: bool = True):
    """Darwin Core -> Standorttabelle. Bei vollstaendigen Artenlisten gelten Begehungen ohne Zielart als Fehlen."""
    df = df.copy()
    if "locationID" not in df:
        df["locationID"] = (df["decimalLatitude"].round(5).astype(str) + "_" + df["decimalLongitude"].round(5).astype(str))
    if "eventID" not in df:
        df["eventID"] = df["locationID"].astype(str) + "_" + df.get("eventDate", pd.Series("", index=df.index)).astype(str)
    target = df["scientificName"].astype(str).str.strip().str.lower() == species.strip().lower() if species else pd.Series(True, index=df.index)
    st = df["occurrenceStatus"].map(_status) if "occurrenceStatus" in df else pd.Series(1.0, index=df.index)
    cnt = pd.to_numeric(df["individualCount"], errors="coerce") if "individualCount" in df else pd.Series(np.nan, index=df.index)
    det = np.where(target, np.where(np.isnan(st), (cnt.fillna(1) > 0).astype(float), st), 0.0)
    df["_det"] = det
    df["_cnt"] = np.where(target, cnt.fillna(df["_det"]), 0.0)
    if not complete_lists:
        df = df[target]
    df["_eff"] = df["samplingEffort"].map(_effort_minutes) if "samplingEffort" in df else 1.0
    ev = df.groupby(["locationID", "eventID"], sort=False).agg(
        det=("_det", "max"), cnt=("_cnt", "sum"), cmax=("_cnt", "max"), eff=("_eff", "first"),
        lat=("decimalLatitude", "first"), lon=("decimalLongitude", "first"),
        date=("eventDate", "first") if "eventDate" in df else ("_det", "size")).reset_index()
    ev["visit"] = ev.groupby("locationID").cumcount() + 1
    sites = ev.groupby("locationID", sort=False).agg(
        lat=("lat", "first"), lon=("lon", "first"), detected=("det", "max"), count=("cnt", "sum"),
        count_max=("cmax", "max"),
        effort=("eff", "sum"), n_visits=("visit", "max")).reset_index()
    wide = ev.pivot(index="locationID", columns="visit", values="det")
    wide.columns = [f"visit_{c}" for c in wide.columns]
    sites = sites.merge(wide, left_on="locationID", right_index=True, how="left")
    sites["x"], sites["y"] = _to_project_xy(sites.rename(columns={"lon": "decimalLongitude", "lat": "decimalLatitude"}), crs)
    has_absence = (sites["detected"] == 0).any()
    return sites, bool(has_absence), df


def read_camtrap_dp(folder, species: str, crs: str):
    """Camtrap DP: Aufwand = Kameratage je Deployment; Antwort = Anzahl unabhaengiger Ereignisse."""
    folder = Path(folder)
    if folder.is_file():
        folder = folder.parent
    dep = pd.read_csv(folder / "deployments.csv")
    obs = pd.read_csv(folder / "observations.csv")
    start = pd.to_datetime(dep["deploymentStart"], utc=True, errors="coerce")
    end = pd.to_datetime(dep["deploymentEnd"], utc=True, errors="coerce")
    dep["effort"] = (end - start).dt.total_seconds() / 86400.0
    o = obs[obs.get("observationType", "animal").astype(str).eq("animal")] if "observationType" in obs else obs
    o = o[o["scientificName"].astype(str).str.lower() == species.lower()]
    ev_col = "eventID" if "eventID" in o else ("sequenceID" if "sequenceID" in o else None)
    n = o.groupby("deploymentID")[ev_col].nunique() if ev_col else o.groupby("deploymentID").size()
    sites = dep.rename(columns={"deploymentID": "locationID_dep"}).copy()
    sites["count"] = sites["locationID_dep"].map(n).fillna(0)
    sites["detected"] = (sites["count"] > 0).astype(float)
    sites["locationID"] = sites.get("locationID", sites["locationID_dep"]).fillna(sites["locationID_dep"])
    sites["n_visits"] = 1
    sites["x"], sites["y"] = _to_project_xy(sites, crs, lon="longitude", lat="latitude")
    sites = sites.rename(columns={"latitude": "lat", "longitude": "lon"})
    return sites[["locationID", "lat", "lon", "x", "y", "count", "detected", "effort", "n_visits"]]


def _site_key_from_file(f):
    p = Path(str(f))
    return p.parent.name if p.parent.name not in ("", ".") else p.stem.split("_")[0]


def read_acoustic(path, sites_path, species: str, crs: str, fmt: str, threshold: float | None = None):
    """BirdNET oder BatDetect2: Erkennungen ueber Schwelle -> Nachweis je Standort; Aufwand = Aufnahmen."""
    files = sorted(Path().glob(path)) if any(ch in str(path) for ch in "*?") else [Path(path)]
    df = pd.concat([pd.read_csv(f, sep=None, engine="python").assign(_srcfile=str(f)) for f in files], ignore_index=True)
    if fmt == "birdnet":
        name_col = next(c for c in df.columns if c.lower() in ("scientific name", "scientific_name"))
        conf = pd.to_numeric(df[next(c for c in df.columns if c.lower() == "confidence")], errors="coerce")
        thr = 0.7 if threshold is None else threshold
        file_col = next((c for c in df.columns if c.lower() in ("file", "begin path", "begin file")), "_srcfile")
    else:  # batdetect2
        name_col = "class"
        conf = pd.to_numeric(df["class_prob"], errors="coerce") * pd.to_numeric(df.get("det_prob", 1.0), errors="coerce")
        thr = 0.5 if threshold is None else threshold
        file_col = next((c for c in df.columns if c.lower() in ("file", "file_name", "filename", "id_file")), "_srcfile")
    df["locationID"] = df["locationID"] if "locationID" in df else df[file_col].map(_site_key_from_file)
    hit = (df[name_col].astype(str).str.lower() == species.lower()) & (conf >= thr)
    st = pd.read_csv(sites_path)
    rec = df.groupby("locationID")[file_col].nunique()
    det = df[hit].groupby("locationID").size()
    st["count"] = st["locationID"].map(det).fillna(0)
    st["detected"] = (st["count"] > 0).astype(float)
    if "effort" not in st:
        st["effort"] = st["locationID"].map(rec).fillna(0)
    st["n_visits"] = 1
    if "x" not in st:
        st["x"], st["y"] = _to_project_xy(st, crs, lon="longitude" if "longitude" in st else "decimalLongitude",
                                          lat="latitude" if "latitude" in st else "decimalLatitude")
    note = f"{fmt}: Schwelle {thr} auf {'Konfidenz' if fmt == 'birdnet' else 'class_prob x det_prob'}; Fehlalarme moeglich, Stichprobe manuell pruefen."
    return st, note


# ---------------------------------------------------------------- Hauptfunktion
def load_observations(cfg: dict, species: str, crs: str, base: Path = Path("."), area_geom=None,
                      period: dict | None = None, sensitive_extra=None) -> Observations:
    fmt = cfg.get("format", "dwc").lower()
    path = base / cfg["path"]
    issues, notes = [], []
    background = None
    if fmt in ("dwc", "darwincore", "csv", "gpkg"):
        raw = read_table(path)
        missing = {"decimalLatitude", "decimalLongitude"} - set(raw.columns)
        if missing:
            raise ValueError(f"Darwin-Core-Spalten fehlen: {sorted(missing)}")
        sites, has_abs, used = sites_from_dwc(raw, species, crs, cfg.get("complete_lists", True))
        issues += plausibility(raw, period)
        others = raw[raw["scientificName"].astype(str).str.lower() != species.lower()] if "scientificName" in raw else raw.iloc[:0]
        if len(others):
            bx, by = _to_project_xy(others, crs)
            background = pd.DataFrame(dict(x=bx, y=by))
    elif fmt in ("camtrapdp", "camtrap", "camtrap-dp"):
        sites = read_camtrap_dp(path, species, crs)
        has_abs = (sites["detected"] == 0).any()
        notes.append("Camtrap DP: Aufwand = Kameratage; Antwort = unabhaengige Ereignisse.")
    elif fmt in ("birdnet", "batdetect2"):
        sites, note = read_acoustic(str(path), base / cfg["sites"], species, crs, fmt, cfg.get("threshold"))
        has_abs = (sites["detected"] == 0).any()
        notes.append(note)
    else:
        raise ValueError(f"Unbekanntes Format: {fmt}")

    # Datentyp
    dtype = cfg.get("type", "auto")
    if dtype == "auto":
        if not has_abs:
            dtype = "presence_only"
        elif fmt in ("camtrapdp", "camtrap", "camtrap-dp") or (sites.get("count_max", sites["count"]) > 1).mean() > 0.1:
            dtype = "counts"
        else:
            dtype = "presence_absence"
    sites["response"] = sites["detected"] if dtype != "counts" else sites["count"]
    if dtype == "presence_only":
        sites = sites[sites["detected"] > 0]
    sites["effort"] = pd.to_numeric(sites["effort"], errors="coerce").fillna(1.0).replace(0, np.nan).fillna(1.0)

    # Lage pruefen
    if area_geom is not None:
        import shapely
        inside = shapely.contains_xy(area_geom, sites["x"].values, sites["y"].values)
        if (~inside).any():
            issues.append(f"{int((~inside).sum())} Standorte liegen ausserhalb des Gebiets und werden ignoriert.")
            sites = sites[inside]
    bad = ~np.isfinite(sites["x"]) | ~np.isfinite(sites["y"])
    if bad.any():
        issues.append(f"{int(bad.sum())} Standorte ohne gueltige Koordinaten entfernt.")
        sites = sites[~bad]
    dup = sites.duplicated(["x", "y"]).sum()
    if dup:
        issues.append(f"{int(dup)} Standorte mit identischen Koordinaten (Pseudo-Replikation?).")
    sens = is_sensitive(species, sensitive_extra)
    return Observations(sites=sites.reset_index(drop=True), dtype=dtype, species=species, source_format=fmt,
                        crs=crs, background=background, issues=issues, sensitive=sens, notes=notes)


def plausibility(df: pd.DataFrame, period: dict | None = None) -> list[str]:
    out = []
    lat = pd.to_numeric(df.get("decimalLatitude"), errors="coerce")
    lon = pd.to_numeric(df.get("decimalLongitude"), errors="coerce")
    if ((lat.abs() > 90) | (lon.abs() > 180)).any():
        out.append("Koordinaten ausserhalb gueltiger Grenzen (Breite/Laenge vertauscht?).")
    if "eventDate" in df:
        d = pd.to_datetime(df["eventDate"].astype(str).str[:10], errors="coerce")
        if d.isna().any():
            out.append(f"{int(d.isna().sum())} Eintraege ohne lesbares Datum.")
        if (d > pd.Timestamp.now()).any():
            out.append("Datum in der Zukunft gefunden.")
        if period:
            s, e = pd.Timestamp(period.get("start", "1900-01-01")), pd.Timestamp(period.get("end", "2100-01-01"))
            n_out = int(((d < s) | (d > e)).sum())
            if n_out:
                out.append(f"{n_out} Eintraege liegen ausserhalb des Projektzeitraums (zeitlicher Versatz zu den Fernerkundungsdaten).")
    if "coordinateUncertaintyInMeters" in df:
        u = pd.to_numeric(df["coordinateUncertaintyInMeters"], errors="coerce")
        if (u > 250).any():
            out.append(f"{int((u > 250).sum())} Eintraege mit Lageunsicherheit > 250 m.")
    return out


def coarsen_xy(x, y, cell_m: float):
    """Vergroebert Koordinaten auf Zellmittelpunkte eines cell_m-Rasters (fuer Veroeffentlichung)."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    return (np.floor(x / cell_m) + 0.5) * cell_m, (np.floor(y / cell_m) + 0.5) * cell_m


def occupancy_null(visits: np.ndarray):
    """Einfaches Occupancy-Modell ohne Kovariaten (MacKenzie et al. 2002), ML-Schaetzung.

    visits: Standorte x Begehungen (0/1, NaN = nicht begangen).
    Rueckgabe: psi (Besetzung), p (Nachweis je Begehung), naive Besetzungsrate.
    """
    from scipy.optimize import minimize
    V = np.asarray(visits, float)
    K = np.isfinite(V).sum(1)
    d = np.nansum(V, 1)
    ok = K > 0
    K, d = K[ok], d[ok]

    def nll(th):
        psi, p = 1 / (1 + np.exp(-th))
        lik_det = psi * p ** d * (1 - p) ** (K - d)
        lik = np.where(d > 0, lik_det, lik_det + (1 - psi))
        return -np.sum(np.log(np.clip(lik, 1e-300, None)))

    r = minimize(nll, x0=[0.0, 0.0], method="Nelder-Mead")
    psi, p = 1 / (1 + np.exp(-r.x))
    return dict(psi=float(psi), p=float(p), naive=float((d > 0).mean()), mean_visits=float(K.mean()),
                p_cum=float(1 - (1 - p) ** K.mean()))


def visit_matrix(sites: pd.DataFrame):
    cols = sorted([c for c in sites.columns if c.startswith("visit_")], key=lambda c: int(c.split("_")[1]))
    return sites[cols].values if cols else None


def read_area(path, crs):
    import geopandas as gpd
    g = gpd.read_file(path)
    if g.crs is None:
        g = g.set_crs(crs)
    g = g.to_crs(crs)
    return g.geometry.union_all() if hasattr(g.geometry, "union_all") else g.unary_union


def camtrap_package_stub(folder):
    """Hilfsfunktion fuer Tests: Minimal-datapackage.json schreiben."""
    Path(folder, "datapackage.json").write_text(json.dumps({"profile": "camtrap-dp", "resources": [
        {"name": "deployments", "path": "deployments.csv"}, {"name": "observations", "path": "observations.csv"}]}))
