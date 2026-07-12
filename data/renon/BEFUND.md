# Renon / ICOS IT-Ren — E57-Befund (offene Prüffrage aus PROJEKT.md §6)

**Datum:** 2026-07-10
**Quelle:** Zenodo `10.5281/zenodo.17186174`, CC-BY-4.0
**Geprüfte Datei:** `2024-11-13-leicaBLK360-icos-CP2.zip` → `e57_setup_archive.zip` → `Renon cp2- Setup 001.e57` (178 MB, 1 von 54 Setups)

## Ergebnis: Fall 2 von 3 — `pinholeRepresentation` + Pose

Die E57-Dateien **enthalten eingebettete Bilder** (`images2D`). Konkret pro Setup:

- **6 Pinhole-Kameras**, je **2048 × 2048 px** (4,2 MP), JPEG eingebettet (~130–630 KB)
- Intrinsics: `focalLength` 6,141 mm, `pixelWidth/Height` 6 µm, Hauptpunkt (1023.5, 1023.5) → **~90° HFOV je Kamera**
- Anordnung: 4 Seitenkameras (~90° versetzt) + Zenit + Nadir → volle Sphäre
- **Volle Pose je Bild**: Quaternion (w,x,y,z) + Translation. Alle 6 teilen denselben Ursprung
  `t = (31.80, −4.56, 3.86)` im Punktwolken-Koordinatensystem des Setups.

→ Damit gilt der in PROJEKT.md §6 beschriebene Fall:
> *„pinholeRepresentation + Pose → besser als Panorama, direkte Projektion; für Layer 1 mit Hugin stitchen"*

Kein fertiges sphärisches Panorama geliefert, aber alles zum Stitchen/Rückprojizieren da.

## Punktwolke (data3D)

Prototype-Felder: `cartesianX/Y/Z, intensity, colorRed/Green/Blue, rowIndex, columnIndex, cartesianInvalidState`
→ **RGB pro Punkt: JA.** Setup 001: 7.789.582 Punkte.

## Konsequenz für die Pipeline

- **Layer 1 (Panorama):** die 6 Pinholes je Setup mit Hugin zu Equirectangular stitchen
  (gemeinsamer Ursprung, Posen bekannt → Kontrollpunktsuche trivial, ggf. Posen als Startwerte).
- **Layer 3-Einfärbung:** direktes Sampling aus der RGB-Wolke (PROJEKT.md §4, empfohlener Weg)
  ist möglich — RGB liegt pro Punkt vor.
- **Koregistrierung Bild↔Wolke:** geschenkt, da Kamera-Pose im Wolken-KS mitgeliefert.

## Reproduktion

```bash
URL="https://zenodo.org/api/records/17186174/files/2024-11-13-leicaBLK360-icos-CP2.zip/content"
# nur die erste E57 aus dem verschachtelten ZIP streamen (~150 MB statt 9,5 GB):
python scripts/zip_remote.py getnested "$URL" e57_setup_archive.zip .e57 data/renon/e57 1
# Bilder + Posen extrahieren:
python scripts/e57_extract_images.py "data/renon/e57/Renon cp2- Setup 001.e57" data/renon/extracted
```

Für weitere Setups `getnested`-Aufruf mit höherem `max_n` (streamt sequenziell durch das
innere ZIP). Ganze Kampagne (54 Setups, 8,5 GB): das äußere Mitglied einmal komplett laden.

## Layer 1 gebaut (2026-07-10)

Aus den 6 Pinholes + Posen wurde ein Equirectangular-Panorama rekonstruiert — **ohne**
Hugin/Kontrollpunkte, per direkter sphärischer Reprojektion:

```bash
python scripts/reproject_pano.py \
  "data/renon/extracted/Renon cp2- Setup 001_poses.json" \
  data/renon/extracted output/renon_setup01/pano_equirect.jpg --w 8192 --sx 1 --sy -1
```

- Konvention (empirisch, img5=oben/img6=unten): R = Kamera→Welt, optische Achse = Kamera −Z,
  Welt z = oben, Bildachsen `--sx 1 --sy -1`. Brennweite = 1023,5 px → exakt 90° HFOV.
- Ergebnis `output/renon_setup01/pano_equirect.jpg` (8192×4096, ~74,5 % Abdeckung; Rest = Nadir).
- Viewer: `viewer/renon.html` (Pannellum). Lokal: `python -m http.server 8360` → `/viewer/renon.html`.
- Offen: Nadir-Retusche (`scripts/nadir_tool.py`), Zenit-Band leicht verwaschen, Multi-Setup-Tour.

## Layer 2 gebaut (2026-07-12)

RGB-Punktwolke direkt aus derselben E57 (via `pye57`, kein Download, kein PotreeConverter),
rezentriert auf den **identischen Ursprung** wie Layer 1 → beide Layer überlagern sich exakt.

```bash
python scripts/e57_to_pointsbin.py "data/renon/e57/Renon cp2- Setup 001.e57" \
  viewer/data/renon_setup01_points.bin --max 2000000
```

- 7,79 Mio. Punkte gelesen, auf 2,0 Mio. zufalls-ausgedünnt (30 MB Web-Binär, Format `PCB1`:
  Magic+uint32 count + float32[N·3] pos + uint8[N·3] rgb). z-up (E57) → y-up (three.js).
- Viewer `viewer/points.html` (three.js 0.160, OrbitControls). Rendern verifiziert:
  34,7 % Punkt-Pixel, mittlere Farbe [136,133,123] (Rinde/Laub/Boden), BBox-Radius 30,6 m.
  Vorschau: `data/renon/layer2_view.jpg`.
- Offen: volle 7,79 Mio. Punkte / echte Potree-Octree (LOD), Multi-Setup-Merge, First-Person
  (PointerLockControls), Panorama als Skybox über der Wolke (Layer 1+2 kombiniert).

## Hinweis: `e57_inspect.R`

Die R-Variante segfaultet unter Windows (R 4.4.2) reproduzierbar bereits beim XML-Lesen
(`xml2`/`readBin`). Ersetzt durch `scripts/e57_extract_images.py` (gleiche Logik,
CRC-seitenkorrekt). R-Ursache noch offen — für den Zweck hier nicht nötig.
