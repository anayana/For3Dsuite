# Geo-Anreicherung — 360-Panorama + Koordinate → Provenienz-Record

Reichert ein georeferenziertes 360°-Panorama automatisch mit **frei verfügbaren**
Geodaten an und trennt dabei sauber, worauf jede Aussage beruht. Kernidee: vier
Provenienz-Ebenen, jeder abgeleitete Wert trägt Quelle, Lizenz und (wo sinnvoll)
Konfidenz.

```
[Panorama + Koordinate]
        │
        ├── Bildanalyse (lokal)         scripts/image_analyze.py
        │     → Kronenschluss/Gap Fraction, Greenness (VARI/GLI/ExG), Sonnenstand
        │
        └── Geo-Anreicherung (lon/lat)  scripts/geo_enrich.py
              ├── SoilGrids v2.0   (REST)  Boden        CC-BY-4.0
              ├── Open-Elevation   (REST)  Relief       frei (SRTM)
              ├── OpenStreetMap    (Overpass) Kontext   ODbL
              └── lokale GeoTIFF   (--raster) Klima/Arten  je nach Quelle
        │
        ▼
[Record: observed / image_derived / geo_enriched / measured_inventory]
```

## Provenienz-Ebenen

| Ebene | Herkunft | befüllt durch |
|---|---|---|
| `observed` | direkt aus dem Bild, qualitativ | (extern / teils Bildanalyse) |
| `image_derived` | algorithmisch aus dem Bild | `image_analyze.py` |
| `geo_enriched` | per Koordinate aus Fremdquellen | `geo_enrich.py` |
| `measured_inventory` | echte Feld-/LiDAR-Inventur | später (leeres Skelett) |

## Nutzung

```bash
# nur Geo (freie Punkt-APIs):
python scripts/geo_enrich.py --lon 8.79 --lat 47.62 --id polyhaven:mossy_forest \
    --provider "Poly Haven" --license CC0 --out record.json

# plus Bildanalyse + lokale Raster (WorldClim/Baumartenkarte):
python scripts/geo_enrich.py --lon 8.79 --lat 47.62 \
    --pano pano.jpg \
    --raster bio1=worldclim/bio1.tif --raster arten=thuenen_arten.tif@1 \
    --out record.json

# an eine bestehende scene.json anhängen (unter scene["metadata"]):
python scripts/geo_enrich.py --scene pfad/zu/scene.json
```

Nur `numpy`/`Pillow` nötig; `--raster` braucht zusätzlich `rasterio`
(und `pyproj` nur bei nicht-geographischem CRS). Fällt eine Online-Quelle aus
(z. B. Overpass im 504), trägt ihr Block ein `error`-Feld und der restliche
Record wird trotzdem gebaut.

## Ehrliche Grenzen

- **RGB-only:** kein echtes NDVI (kein NIR) — Greenness sind sichtbare Proxys.
- **Himmel/Gap Fraction** per Helligkeits-/Blau-Heuristik, kein SAM/Canopy-Modell.
- **`species_guess` / `leaf_type_visual` / `depth_map_ref`** bleiben `null` — sie
  bräuchten VLM/CLIP bzw. Depth-Anything; bewusst nicht vorgetäuscht (Haken offen).
- **`geo_enriched`** sind **modellierte Kartenwerte**, keine gemessenen
  Bestandeswerte am Punkt. Belastbare Inventur kommt allein aus
  `measured_inventory` (LiDAR + Feld).
