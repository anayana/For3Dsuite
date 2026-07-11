# 360° Panorama Workflow (Open Source)

Kompletter Workflow von 6 Fisheye-Einzelbildern zum interaktiven 360°/3D-Viewer im Browser.

**Live-Demo (GitHub Pages):** https://anayana.github.io/For3Dsuite/ — statischer
Export der Gallery ([docs/](docs/), erzeugt mit
[export_static.py](platform/dev/export_static.py)): Renon-Laserscan-Szene mit
87 automatisch abgeleiteten Bauminventur-Markern und 3D-Punktwolke, Hechingen-
Fisheye-Szene. Upload/Verarbeitung brauchen den selbst gehosteten Stack
([platform/](platform/README.md)).

```
6 Fisheye-Fotos  →  Hugin (Stitching)  →  Equirectangular-Panorama  →  Pannellum (Web-Viewer)
```

## Ordnerstruktur

```
360Pano3D/
├── input/
│   └── scene01/          <- hier die 6 Einzelbilder einer Szene ablegen
├── output/
│   └── scene01/          <- fertiges Panorama landet hier (pano_equirect.jpg)
├── scripts/
│   ├── stitch.ps1        <- Hugin-Batch-Stitching (Kernstück)
│   └── tile_pano.ps1     <- optional: Multires-Tiles für sehr große Panoramen
└── viewer/
    └── index.html        <- Pannellum-Viewer, öffnet output/scene01/pano_equirect.jpg
```

## Voraussetzungen (einmalig installieren)

1. **[Hugin](https://hugin.sourceforge.io/download/)** (Windows-Installer) – enthält die
   Kommandozeilen-Tools `pto_gen`, `pto_var`, `cpfind`, `cpclean`, `linefind`,
   `autooptimiser`, `pano_modify`, `nona`, `enblend`. Standardpfad:
   `C:\Program Files\Hugin\bin`.
2. Optional für Multires-Tiling: **Python 3** + `pip install Pillow`, sowie einmalig
   `git clone --depth 1 https://github.com/mpetroff/pannellum.git`.
3. Zum Anschauen: jeder moderne Browser (Chrome, Edge, Firefox) – kein Server nötig,
   `viewer/index.html` kann direkt per Doppelklick geöffnet werden (Chrome ggf. mit
   `--allow-file-access-from-files` starten, falls das Bild nicht lädt; Firefox
   funktioniert i.d.R. direkt).

## Schritt 1 – Bilder ablegen

6 Fisheye-/Weitwinkelbilder einer Szene nach `input/scene01/` kopieren
(Dateinamen egal, werden alphabetisch sortiert eingelesen).

## Schritt 2 – Stitching

```powershell
cd 360Pano3D\scripts
.\stitch.ps1 -SceneDir ..\input\scene01 -OutDir ..\output\scene01
```

Wichtige Parameter (bei Bedarf anpassen):

- `-LensType` – Projektion der Eingabebilder: `2` = Circular Fisheye, `3` = Full-frame
  Fisheye (Default), `0` = rectilinear/normal.
- `-Fov` – horizontales Sichtfeld eines Einzelbildes in Grad, laut Objektiv (Default `180`).
- `-HuginBin` – falls Hugin nicht im PATH liegt, z.B. `-HuginBin "C:\Program Files\Hugin\bin"`.

Das Skript durchläuft automatisch: Projekt anlegen → Kontrollpunkte finden →
Ausreißer bereinigen → Linien geraderichten → optimieren (Position/Belichtung/Horizont)
→ auf Equirectangular 360×180 setzen → remappen → nahtlos verschmelzen.

Ergebnis: `output/scene01/pano_equirect.jpg`

**Tipp:** Bei schwierigen Szenen (wenig Kontrast, Bewegung zwischen den Aufnahmen)
lohnt sich ein Blick in die Hugin-GUI (`hugin project.pto` im `_work`-Ordner öffnen),
um Kontrollpunkte manuell zu prüfen oder zu ergänzen.

## Schritt 3 (optional) – Multiresolution-Tiling

Nur nötig bei sehr hochauflösenden Panoramen (>8000 px Breite), damit der Browser nicht
ein einzelnes Riesenbild laden muss:

```powershell
.\tile_pano.ps1 -PanoFile ..\output\scene01\pano_equirect.jpg `
                -OutDir ..\viewer\img\scene01_tiles `
                -PannellumRepo C:\pfad\zu\pannellum
```

Die Ausgabe enthält einen `multiRes`-Konfigurationsblock, den man in
`viewer/index.html` einsetzt (Vorlage dort bereits als Kommentar hinterlegt).

## Schritt 4 – Ansehen

`viewer/index.html` im Browser öffnen (oder per lokalem Server, z.B.
`npx serve viewer`). Zeigt das Panorama in Pannellum mit Zoom, Vollbild und Kompass.

Für mehrere Szenen (begehbare Tour): in `index.html` unter `"scenes"` weitere Einträge
(`scene02`, `scene03`, ...) ergänzen und per `hotSpots` (Typ `"scene"`) verknüpfen.

## Stereo-3D-Workflow (echtes 3D für VR)

Wenn pro Szene zusätzlich ein `left/`- und `right/`-Bildsatz existiert (Stereo-Rig,
je 6 Positionen × 3 Belichtungen), lässt sich ein stereoskopisches 360°-Panorama bauen:

```powershell
# 1. RAW-Entwicklung (mittlere Belichtung je Position, --half = schneller Test)
python scripts\develop_raw.py input\scene01_left  --half <6 linke ARWs>
python scripts\develop_raw.py input\scene01_right --half <6 rechte ARWs>

# 2. Beide Augen einzeln stitchen
.\scripts\stitch.ps1 -SceneDir .\input\scene01_left  -OutDir .\output\scene01_left  -Fov 107
.\scripts\stitch.ps1 -SceneDir .\input\scene01_right -OutDir .\output\scene01_right -Fov 107

# 3. Zu Top-Bottom-Stereo kombinieren (links oben, rechts unten)
python scripts\combine_stereo.py output\scene01_left\pano_equirect.jpg `
    output\scene01_right\pano_equirect.jpg output\scene01\pano_stereo_tb.jpg

# 4. Ansehen: viewer\vr.html (A-Frame/WebXR) - am Desktop monoskopisch,
#    mit VR-Brille bekommt jedes Auge seine Bildhaelfte -> Tiefeneindruck
```

Falls die beiden Augen nicht auf denselben Nullpunkt ausgerichtet sind, beim
Kombinieren `--yaw-offset <Grad>` mitgeben.

## Nadir-Retusche (Stativ entfernen)

Der Boden ist im Equirectangular-Format stark verzerrt - Retusche daher in einer
entzerrten Draufsicht ([nadir_tool.py](scripts/nadir_tool.py)):

```powershell
python scripts\nadir_tool.py extract output\scene01\pano_equirect.jpg nadir.png --fov 120
# Stativ durch geklonte Bodenregion ersetzen (Poisson-Blending, nahtlos):
python scripts\nadir_tool.py clone nadir.png nadir_clean.png --radius 0.20 --dx -320 --dy 330
python scripts\nadir_tool.py insert output\scene01\pano_equirect.jpg nadir_clean.png output\scene01\pano_retouched.jpg --fov 120
```

`--dx/--dy` = Versatz der Klon-Quelle vom Zentrum; `--radius` = Größe des zu
ersetzenden Kreises. Alternativ `inpaint` (automatisch, aber bei Gras-Textur
verwaschener). Wer lieber manuell in GIMP retuschiert: `extract` → in GIMP
bearbeiten (fuer Content-Aware-Fill das Resynthesizer-Plugin installieren) → `insert`.

## Filter-Varianten (GIMP-Batch)

[make_variants.ps1](scripts/make_variants.ps1) erzeugt per GIMP/Script-Fu drei
abgestufte Looks, zwischen denen User im Viewer umschalten können:

```powershell
.\scripts\make_variants.ps1 -PanoFile .\output\scene01\pano_retouched.jpg -OutDir .\output\scene01
```

- `pano_v1_natural.jpg` – dezente Optimierung
- `pano_v2_vivid.jpg` – kräftige Farben, mehr Kontrast
- `pano_v3_warm.jpg` – warmer Look (goldene Stunde)

`viewer/index.html` zeigt unten eine Umschaltleiste (Natur | Kräftig | Warm);
die Blickrichtung bleibt beim Wechsel erhalten.

## Self-Hosting-Plattform (platform/)

Der komplette Workflow läuft auch als selbst gehosteter Web-Stack: Caddy (TLS,
Auth) + Garage (S3-Storage) + FastAPI-App mit Job-Queue und Worker (Hugin,
E57-Reprojektion). Zwei Oberflächen: öffentliche **Gallery** (Szenenauswahl,
Pannellum-Viewer mit klickbaren Inventur-Markern) und zugangsgeschütztes
**Studio** (`/admin`: Upload, Job-Status, Marker-Editor). Marker lassen sich mit
[markers_from_xyz.py](scripts/markers_from_xyz.py) direkt aus
Punktwolken-Koordinaten (z. B. Einzelbaum-Inventuren) berechnen.

Details, Schnellstart (lokal ohne Docker) und Server-Deployment:
[platform/README.md](platform/README.md)

## Qualitative Auswertung + Wachstumsprognose (Bausteine 4 & 5)

Aus der reinen Visualisierung wird eine prognosefähige Bestandesbeschreibung.
Konzept: [BAUSTEINE_4_5_1.md](BAUSTEINE_4_5_1.md).

- **Qualität aus RGB** ([qualitative_rgb.py](scripts/qualitative_rgb.py)): je
  Baum-Marker einen Kronen-Crop aus dem Panorama reprojizieren und klassisch
  (ohne Training) auswerten — Farbindizes (ExG/GLI), GLCM-Textur, bestandes-
  relativer Vitalitätsproxy — und das georeferenzierte Zustandsattribut in die
  `scene.json` zurückschreiben. Über mehrere Setups aggregierbar (Multi-View).
  ```powershell
  python scripts\qualitative_rgb.py --scene scene.json --pano pano.jpg --write --csv vital.csv
  ```
- **Kreuzvalidierung RGB ↔ LiDAR/QSM**
  ([crossvalidate_rgb_lidar.py](scripts/crossvalidate_rgb_lidar.py)): prüft, ob
  RGB-Befund und Struktur am selben Baum übereinstimmen — Widerspruch = Hinweis
  auf Fehldeutung. Spearman-ρ + Widerspruchsliste.
- **Wachstumsprognose** ([growth-service/](growth-service/README.md) +
  [treegross_export.py](scripts/treegross_export.py)): Inventur → TreeGrOSS-
  Baumliste → Simulation (n Jahre) → Zukunftsbestand zurück in die `scene.json`.
  Der Nutzer begeht dann den in *n* Jahren prognostizierten Wald. TreeGrOSS
  (GPLv3) läuft als isolierter Java-Dienst; die Suite spricht ihn nur über
  HTTP/JSON an.

## Nächste Schritte / Ausbaustufen

- **Nachbearbeitung**: GIMP oder darktable für Farbkorrektur, Retusche des Stativ-Nadirs.
- **Batch mehrerer Szenen**: `stitch.ps1` in einer Schleife über alle Unterordner in
  `input/` aufrufen.
- **Echtes 3D (Tiefe/Begehbarkeit)**: für räumliche Rekonstruktion statt reinem
  Rundumblick eignen sich [Meshroom](https://alicevision.org/#meshroom) (Photogrammetrie)
  oder Gaussian-Splatting-Tools (z.B. Nerfstudio) – benötigt aber deutlich mehr als
  6 Bilder pro Szene und ist ein eigenständiger, aufwändigerer Pfad.
