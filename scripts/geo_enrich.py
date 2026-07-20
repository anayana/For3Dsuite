#!/usr/bin/env python3
"""geo_enrich.py -- 360-Panorama per Koordinate mit freien Geodaten anreichern.

Baut pro Panorama einen Metadaten-Record mit vier klar getrennten Provenienz-
Ebenen, damit jederzeit transparent bleibt, worauf eine Aussage beruht:

  observed            direkt aus dem Bild abgelesen (qualitativ)      -> extern befuellt
  image_derived       algorithmisch aus dem Bild berechnet           -> extern befuellt
  geo_enriched        per lon/lat aus freien Fremdquellen (HIER)      -> dieses Skript
  measured_inventory  echte Feld-/LiDAR-Inventur                      -> spaeter

Nur freie, keyless Punkt-APIs (fuer akademische Nutzung geeignet):
  * Boden      SoilGrids v2.0 (ISRIC)      CC-BY 4.0
  * Relief     Open-Elevation (SRTM)       frei   -> Hoehe + Hangneigung/Exposition
  * Kontext    OpenStreetMap / Overpass    ODbL   -> Wald, leaf_type, Schutzgebiet

Jede Quelle scheitert einzeln gutmuetig: faellt eine aus (Netz/Timeout), traegt
ihr Block ein "error"-Feld und der restliche Record wird trotzdem gebaut.

Nutzung:
  python geo_enrich.py --lon 8.79 --lat 47.62 --id polyhaven:mossy_forest \
      --license CC0 --out record.json
  python geo_enrich.py --lon 8.79 --lat 47.62 --scene pfad/zu/scene.json   # anhaengen
"""
import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from datetime import date

UA = {"User-Agent": "For3Dsuite-geoenrich/1.0 (academic research)"}
OVERPASS_MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def _get(url, timeout=25, retries=2):
    """GET -> geparstes JSON oder None (mit letzter Fehlermeldung in _get.last)."""
    last = None
    for _ in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:  # noqa: BLE001 -- bewusst breit, Quelle darf ausfallen
            last = f"{type(e).__name__}: {str(e)[:120]}"
    _get.last = last
    return None


_get.last = None


# ---------------------------------------------------------------- Boden --------
def soil_soilgrids(lon, lat):
    props = ["phh2o", "clay", "sand", "silt", "soc"]
    q = urllib.parse.urlencode(
        [("lon", lon), ("lat", lat), ("depth", "0-5cm"), ("value", "mean")]
        + [("property", p) for p in props])
    data = _get(f"https://rest.isric.org/soilgrids/v2.0/properties/query?{q}", timeout=30)
    block = {"source": "SoilGrids v2.0 (ISRIC)", "license": "CC-BY-4.0", "depth": "0-5cm"}
    if not data:
        block["error"] = _get.last or "keine Antwort"
        return block
    try:
        for layer in data["properties"]["layers"]:
            name = layer["name"]
            d = layer.get("unit_measure", {}).get("d_factor", 1) or 1
            units = layer.get("unit_measure", {}).get("target_units", "")
            val = layer["depths"][0]["values"].get("mean")
            if val is None:
                block[name] = None
                continue
            block[name] = {"value": round(val / d, 2), "units": units}
    except (KeyError, IndexError, TypeError) as e:
        block["error"] = f"Parsing: {e}"
    return block


# ------------------------------------------------------ Relief (Hoehe/Hang) ----
def _elevations(points):
    """open-elevation Mehrpunktabfrage -> Liste der Hoehen (m) in Punktreihenfolge."""
    locs = "|".join(f"{la},{lo}" for lo, la in points)
    data = _get("https://api.open-elevation.com/api/v1/lookup?locations="
                + urllib.parse.quote(locs), timeout=30)
    if not data or "results" not in data:
        return None
    return [r.get("elevation") for r in data["results"]]


def elevation_relief(lon, lat, step_m=30.0):
    """Hoehe am Punkt + Hangneigung/Exposition aus 4 Nachbarn (Zentraldifferenz)."""
    block = {"source": "Open-Elevation (SRTM)", "license": "frei"}
    dlat = step_m / 111320.0
    dlon = step_m / (111320.0 * max(math.cos(math.radians(lat)), 1e-6))
    # Reihenfolge: Zentrum, Nord, Sued, Ost, West
    pts = [(lon, lat), (lon, lat + dlat), (lon, lat - dlat),
           (lon + dlon, lat), (lon - dlon, lat)]
    els = _elevations(pts)
    if not els or any(e is None for e in els):
        block["error"] = _get.last or "keine Hoehendaten"
        return block
    c, n, s, e, w = els
    block["elevation_m"] = round(c, 1)
    dzdx = (e - w) / (2 * step_m)   # +x = Ost
    dzdy = (n - s) / (2 * step_m)   # +y = Nord
    slope = math.degrees(math.atan(math.hypot(dzdx, dzdy)))
    block["slope_deg"] = round(slope, 1)
    if slope >= 0.1:
        asp = (math.degrees(math.atan2(dzdy, -dzdx)) + 360) % 360  # Richtung Gefaelle
        block["aspect_deg"] = round(asp, 0)
    else:
        block["aspect_deg"] = None
    return block


# ------------------------------------------------------- OSM-Kontext -----------
def osm_context(lon, lat, radius_m=400):
    block = {"source": "OpenStreetMap", "license": "ODbL"}
    query = (f"[out:json][timeout:25];("
             f"way(around:{radius_m},{lat},{lon})[landuse=forest];"
             f"way(around:{radius_m},{lat},{lon})[natural=wood];"
             f"relation(around:{radius_m},{lat},{lon})[boundary=protected_area];"
             f");out tags center 20;")
    data = None
    for base in OVERPASS_MIRRORS:
        data = _get(base + "?data=" + urllib.parse.quote(query), timeout=30, retries=1)
        if data is not None:
            break
    if data is None:
        block["error"] = _get.last or "Overpass nicht erreichbar"
        return block
    forest, protected = None, None
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        if tags.get("boundary") == "protected_area" and protected is None:
            protected = tags.get("name") or tags.get("protection_title") or True
        elif (tags.get("landuse") == "forest" or tags.get("natural") == "wood") \
                and forest is None:
            forest = tags
    if forest:
        block["landuse"] = forest.get("landuse") or ("wood" if forest.get("natural") else None)
        block["leaf_type"] = forest.get("leaf_type")
        block["name"] = forest.get("name")
    else:
        block["landuse"] = block["leaf_type"] = block["name"] = None
    block["protected_area"] = protected
    return block


# ---------------------------------------------- lokale Raster (WorldClim etc.) -
def raster_point_sample(path, lon, lat, band=1):
    """Wert eines lokalen GeoTIFF am Punkt. Braucht rasterio (optional),
    pyproj nur bei nicht-geographischem CRS."""
    try:
        import rasterio
    except ImportError:
        return {"error": "rasterio nicht installiert (pip install rasterio)"}
    try:
        with rasterio.open(path) as ds:
            x, y = lon, lat
            if ds.crs is not None and not ds.crs.is_geographic:
                try:
                    from pyproj import Transformer
                    x, y = Transformer.from_crs("EPSG:4326", ds.crs,
                                                always_xy=True).transform(lon, lat)
                except ImportError:
                    return {"error": "pyproj noetig fuer CRS-Transform"}
            row, col = ds.index(x, y)
            if not (0 <= row < ds.height and 0 <= col < ds.width):
                return {"error": "Punkt ausserhalb des Rasters"}
            val = ds.read(band, window=((row, row + 1), (col, col + 1)))[0, 0]
            if ds.nodata is not None and val == ds.nodata:
                val = None
            return {"value": (float(val) if val is not None else None),
                    "band": band, "file": os.path.basename(path),
                    "source": "lokales Raster"}
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {str(e)[:120]}"}


# ------------------------------------------------------- Record-Bau ------------
def build_record(lon, lat, pano_id=None, image_url=None, license="unknown",
                 provider=None, coord_precision_m=None, coord_source=None,
                 pano=None, rasters=None):
    if lon is None or lat is None:
        geo = {"_note": "keine Koordinate vorhanden — nur Bildanalyse"}
    else:
        geo = {"_note": "per Koordinate aus freien Fremdquellen",
               "soil": soil_soilgrids(lon, lat),
               "relief": elevation_relief(lon, lat),
               "osm_context": osm_context(lon, lat),
               "retrieved_at": date.today().isoformat()}
        for label, path, band in (rasters or []):
            geo.setdefault("rasters", {})[label] = raster_point_sample(path, lon, lat, band)

    observed = {"_note": "direkt aus dem Bild (qualitativ)",
                "season": None, "phenology": None, "sun_position": None, "confidence": None}
    image_derived = {"_note": "algorithmisch aus dem Bild (extern befuellt)",
                     "canopy_openness_pct": None, "gap_fraction": None,
                     "greenness_vari": None, "leaf_type_visual": None,
                     "species_guess": None, "depth_map_ref": None}
    if pano:
        from image_analyze import analyze
        image_derived, sun = analyze(pano)
        observed["sun_position"] = sun

    return {
        "id": pano_id,
        "source": {"provider": provider, "license": license, "image_url": image_url},
        "geometry": {"type": "Point", "coordinates": [lon, lat],
                     "coord_precision_m": coord_precision_m, "coord_source": coord_source},
        "observed": observed,
        "image_derived": image_derived,
        "geo_enriched": geo,
        "measured_inventory": {"_note": "leer bis LiDAR + Feld vorliegen",
                               "species_composition": None, "dbh_cm": None,
                               "height_m": None, "basal_area_m2_ha": None,
                               "volume_m3_ha": None, "stand_age_a": None, "source": None},
    }


def summarize(rec):
    g = rec["geo_enriched"]
    print(f"Koordinate: {rec['geometry']['coordinates']}")
    for key, label in (("soil", "Boden"), ("relief", "Relief"), ("osm_context", "OSM")):
        b = g.get(key)
        if b is None:
            continue
        if b.get("error"):
            print(f"  {label:7s}: FEHLER ({b['error']})")
        elif key == "soil":
            ph = (b.get("phh2o") or {}).get("value")
            print(f"  {label:7s}: pH {ph}, Ton {(b.get('clay') or {}).get('value')}%, "
                  f"Sand {(b.get('sand') or {}).get('value')}%, "
                  f"C {(b.get('soc') or {}).get('value')} {(b.get('soc') or {}).get('units','')}")
        elif key == "relief":
            print(f"  {label:7s}: {b.get('elevation_m')} m, Hang {b.get('slope_deg')}°, "
                  f"Exposition {b.get('aspect_deg')}°")
        else:
            print(f"  {label:7s}: landuse={b.get('landuse')}, leaf_type={b.get('leaf_type')}, "
                  f"Name={b.get('name')}, Schutzgebiet={b.get('protected_area')}")
    for label, b in (g.get("rasters") or {}).items():
        print(f"  Raster {label}: {b.get('error') or b.get('value')}")
    idv = rec["image_derived"]
    if idv.get("gap_fraction") is not None:
        print(f"  Bild   : Kronenschluss offen {idv['canopy_openness_pct']}%, "
              f"ExG {idv.get('greenness_exg')}, GLI {idv.get('greenness_gli')}")
        sun = rec["observed"].get("sun_position") or {}
        print(f"  Sonne  : Azimut {sun.get('azimuth_deg')}°, Hoehe {sun.get('elevation_deg')}° "
              f"(Konfidenz {sun.get('confidence')})")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lon", type=float, help="Laengengrad")
    ap.add_argument("--lat", type=float, help="Breitengrad")
    ap.add_argument("--id")
    ap.add_argument("--provider")
    ap.add_argument("--image-url")
    ap.add_argument("--license", default="unknown")
    ap.add_argument("--coord-precision-m", type=float)
    ap.add_argument("--coord-source")
    ap.add_argument("--pano", help="Equirectangular-Panorama -> image_derived + Sonnenstand")
    ap.add_argument("--raster", action="append", default=[], metavar="LABEL=PFAD[@BAND]",
                    help="lokales GeoTIFF am Punkt samplen (mehrfach); z. B. "
                    "--raster bio1=worldclim/bio1.tif --raster arten=thuenen.tif@1")
    ap.add_argument("--out", help="Record als JSON-Datei schreiben")
    ap.add_argument("--scene", help="scene.json: lon/lat aus geometry lesen (falls "
                    "vorhanden) und Record unter scene['metadata'] anhaengen")
    args = ap.parse_args()

    scene = None
    lon, lat = args.lon, args.lat
    pano = args.pano
    if args.scene:
        scene = json.loads(open(args.scene, encoding="utf-8").read())
        geom = (scene.get("geometry") or {}).get("coordinates")
        gps = (scene.get("source") or {}).get("gps") or {}
        if lon is None and geom:
            lon, lat = geom[0], geom[1]
        elif lon is None and gps.get("lat") is not None:   # Poly-Haven: source.gps
            lon, lat = gps["lon"], gps["lat"]
        # Pano automatisch neben der scene.json nehmen, falls nicht angegeben
        if pano is None:
            cand = os.path.join(os.path.dirname(os.path.abspath(args.scene)), "pano.jpg")
            if os.path.isfile(cand):
                pano = cand
        if args.id is None:
            args.id = scene.get("id")
        if args.license == "unknown":
            args.license = (scene.get("source") or {}).get("license", "unknown")
    if (lon is None or lat is None) and not pano:
        sys.exit("--lon/--lat angeben (oder --scene mit geometry.coordinates/source.gps "
                 "bzw. --pano fuer reine Bildanalyse)")
    if lon is None or lat is None:
        print("Hinweis: keine Koordinate — nur Bildanalyse (geo_enriched bleibt leer)")

    rasters = []
    for spec in args.raster:
        if "=" not in spec:
            sys.exit(f"--raster erwartet LABEL=PFAD[@BAND], nicht {spec!r}")
        label, path = spec.split("=", 1)
        band = 1
        if "@" in path:
            path, b = path.rsplit("@", 1)
            band = int(b)
        rasters.append((label, path, band))

    rec = build_record(lon, lat, pano_id=args.id or (scene or {}).get("id"),
                       image_url=args.image_url, license=args.license,
                       provider=args.provider, coord_precision_m=args.coord_precision_m,
                       coord_source=args.coord_source, pano=pano, rasters=rasters)
    summarize(rec)

    if scene is not None:
        scene["metadata"] = rec
        open(args.scene, "w", encoding="utf-8").write(
            json.dumps(scene, ensure_ascii=False, indent=2))
        print(f"-> an {args.scene} angehaengt (scene['metadata'])")
    elif args.out:
        open(args.out, "w", encoding="utf-8").write(
            json.dumps(rec, ensure_ascii=False, indent=2))
        print(f"-> {args.out}")
    else:
        print(json.dumps(rec, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
