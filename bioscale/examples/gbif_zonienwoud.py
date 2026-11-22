"""Echtes Beispiel: eBird-Checklisten aus GBIF im Zonienwoud / Foret de Soignes (Bruessel, buchendominiert)
+ Sentinel-2 + Copernicus DEM + ESA WorldCover.

Aufruf:   python examples/gbif_zonienwoud.py [zielordner] [--ohne-sentinel2]
Braucht Internet (api.gbif.org, earth-search.aws.element84.com, S3-Buckets Sentinel/DEM/WorldCover).

Rechnet zwei Fragen mit denselben Daten:
  1. Kleiber (Sitta europaea): Vorkommen/Fehlen je Ort, Begehungen = Checklisten -> auch Occupancy-Modell.
  2. Artenzahl der Voegel je Ort, rarefiziert auf gleich viele Checklisten.

Datenwahl (begruendet):
  * Nur der GBIF-Datensatz "eBird" (Lizenz CC BY 4.0). Er hat Checklisten-ID (eventID) und Orts-ID
    (locality). Damit ist eine Checkliste ohne Kleiber ein "nicht gefunden" (Annahme: vollstaendige Liste).
  * Andere Quellen im Gebiet sind fuer Punktmodelle ungeeignet: waarnemingen.be ist auf 5 km vergroebert
    (Unsicherheit 3536 m), ABV auf 1 km; iNaturalist ist teils CC BY-NC.
  * Wandernde Zaehlungen (traveling counts) haben nur den Startpunkt -> Raster 50 m, Lagefehler moeglich.
  * Fuer Veroeffentlichungen: GBIF-Download mit DOI ueber die Download-API zitieren.
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd
import yaml

EBIRD = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
# Zonienwoud mit Randbereichen (WGS84)
BBOX = (4.36, 50.74, 4.48, 50.81)
CRS = "EPSG:31370"  # Belgian Lambert 72
YEARS = "2015,2025"
SPECIES = "Sitta europaea"


def gbif_all(params, log=print):
    rows, off = [], 0
    while True:
        q = dict(params, limit=300, offset=off)
        url = "https://api.gbif.org/v1/occurrence/search?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, headers={"User-Agent": "bioscale-beispiel"})
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        rows += d["results"]
        off += 300
        if d.get("endOfRecords") or off >= 100000:
            break
        if off % 3000 == 0:
            log(f"  GBIF: {len(rows)} von {d['count']}")
    return rows


def main(out="gbif_zonienwoud", *flags):
    out = Path(out)
    (out / "daten").mkdir(parents=True, exist_ok=True)
    lo0, la0, lo1, la1 = BBOX
    geo = f"POLYGON(({lo0} {la0},{lo1} {la0},{lo1} {la1},{lo0} {la1},{lo0} {la0}))"
    csv = out / "daten" / "ebird_voegel_dwc.csv"
    if not csv.exists():
        rows = gbif_all({"datasetKey": EBIRD, "classKey": 212, "geometry": geo, "year": YEARS,
                         "hasCoordinate": "true", "hasGeospatialIssue": "false"})
        df = pd.DataFrame([{
            "occurrenceID": r.get("occurrenceID"), "gbifID": r.get("gbifID"),
            "scientificName": r.get("species") or r.get("scientificName"),
            "occurrenceStatus": "present", "individualCount": r.get("individualCount"),
            "decimalLatitude": r["decimalLatitude"], "decimalLongitude": r["decimalLongitude"],
            "eventDate": str(r.get("eventDate", ""))[:10], "eventID": r.get("eventID"),
            "locationID": r.get("locality"), "license": r.get("license"), "datasetName": r.get("datasetName"),
        } for r in rows])
        df = df.dropna(subset=["eventID", "locationID", "scientificName"])
        df.to_csv(csv, index=False)
    df = pd.read_csv(csv)
    print(f"eBird ueber GBIF: {len(df)} Nachweise, {df.eventID.nunique()} Checklisten, "
          f"{df.locationID.nunique()} Orte, {df.scientificName.nunique()} Arten")
    # Orte mit mindestens 2 Checklisten (sonst kein Fehlen/Occupancy sinnvoll)
    n_cl = df.groupby("locationID").eventID.nunique()
    keep = n_cl[n_cl >= 2].index
    df = df[df.locationID.isin(keep)]
    # Ortskoordinate = Median der Checklisten (eBird-Orte sind feste Punkte, kleine Abweichungen moeglich)
    med = df.groupby("locationID")[["decimalLatitude", "decimalLongitude"]].median()
    df = df.drop(columns=["decimalLatitude", "decimalLongitude"]).merge(med, left_on="locationID", right_index=True)
    # hoechstens 10 Checklisten je Ort (sonst dominieren Hotspots)
    first = df.drop_duplicates("eventID").sort_values("eventDate").groupby("locationID").head(10).eventID
    df = df[df.eventID.isin(first)]
    df.to_csv(out / "daten" / "ebird_orte_dwc.csv", index=False)
    print(f"Verwendet: {df.locationID.nunique()} Orte mit >= 2 Checklisten, {df.eventID.nunique()} Checklisten")

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    xs, ys = tr.transform([lo0, lo1, lo0, lo1], [la0, la0, la1, la1])
    minx, miny, maxx, maxy = min(xs), min(ys), max(xs), max(ys)
    area = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::31370"}},
            "features": [{"type": "Feature", "properties": {"name": "Zonienwoud und Umgebung"},
                          "geometry": {"type": "Polygon", "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy],
                                                                           [minx, maxy], [minx, miny]]]}}]}
    (out / "daten" / "gebiet.geojson").write_text(json.dumps(area))
    open_data = {"dem": True, "worldcover": True}
    if "--ohne-sentinel2" not in flags:
        open_data["sentinel2"] = {"cloud_max": 40}
    base = {"area": "daten/gebiet.geojson", "crs": CRS, "resolution_m": 50,
            "period": {"start": "2023-04-01", "end": "2023-09-30"},
            "covariates": {"open": open_data},
            "model": {"candidates": ["glm", "rf"], "bootstrap": 10}}
    p1 = dict(base, name=f"Zonienwoud: {SPECIES} (eBird-Checklisten via GBIF)",
              question={"target": "occurrence", "species": SPECIES, "profile": "voegel_wald"},
              occurrence={"path": "daten/ebird_orte_dwc.csv", "format": "dwc", "complete_lists": True,
                          "type": "presence_absence"},  # eBird-Anzahlen sind keine standardisierten Zaehlungen
              output="ergebnis_kleiber")
    p2 = dict(base, name="Zonienwoud: Artenzahl Voegel (eBird-Checklisten via GBIF)",
              question={"target": "richness", "species": "", "profile": "voegel_wald"},
              occurrence={"path": "daten/ebird_orte_dwc.csv", "format": "dwc", "rarefy_to": 2},
              output="ergebnis_artenzahl")
    from bioscale.pipeline import run
    for name, cfg in (("projekt_kleiber.yml", p1), ("projekt_artenzahl.yml", p2)):
        p = out / name
        p.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False))
        res = run(p)
        print(f"{name}: Ampel {res['ampel']}, Modell {res['best_model']}, Bericht {res['report']}")


if __name__ == "__main__":
    main(*sys.argv[1:])
