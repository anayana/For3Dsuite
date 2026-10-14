# iPad/iPhone-LiDAR → metrischer Gaussian Splat

Low-Cost-Variante des PortalCam-Prinzips (XGRIDS): **LiDAR liefert Maßstab und
Geometrie, Fotos liefern die Optik.** Ergebnis aus einer Aufnahme:

| Datei | Wofür |
|---|---|
| `raum_splat.ply` | fotorealistischer 3D-Gaussian-Splat **in Metern** (Viewer, VR) |
| `raum_lidar_points.ply` | dichte LiDAR-Messwolke (1 cm Raster), **hier wird gemessen** |
| `raum_bericht.json` | Raummaße (Näherung), Ausrichtungs-Kontrolle, Statistik |

Splat und Messwolke liegen deckungsgleich im selben Koordinatensystem
(ARKit: +Y oben, 1 Einheit = 1 m).

**Genauigkeit:** Raummaße typisch ±1–3 cm (iPad-/iPhone-LiDAR, kleiner Raum).
Millimeter sind nicht drin. Messen immer an der LiDAR-Wolke; das
📏-Werkzeug im Splat-Viewer ist eine Näherung (einige cm). Zwei, drei Strecken
mit einem Laser-Entfernungsmesser gegenmessen.

## 1. Aufnahme

**Gerät:** iPhone ab 12 Pro oder iPad Pro ab 2020 (LiDAR). Reichweite ca. 4–5 m.

**App (eine davon, Export mit Posen + Tiefe):**

| App | Export | Format-Kennung |
|---|---|---|
| 3d Scanner App (Laan Labs, kostenlos) | LiDAR-Scan → Export **„All Data"** | `scanner3d` |
| Record3D | Export **„EXR + JPG"** | `record3d` |
| Polycam | **Raw Data** (Developer Mode in den Einstellungen) | `polycam` |
| beliebig | `transforms.json` (nerfstudio) mit `depth_file_path` | `nerfstudio` |
| Apple ARKitScenes (freie iPad-Pro-Daten, siehe unten) | `scripts/arkitscenes_fetch.sh` | `arkitscenes` |

Das Format wird automatisch erkannt (auch eine Ordnerebene tiefer im ZIP).

**Scannen:**
- Langsam gehen. Alle Wände, Boden **und Decke** erfassen, sonst stimmt die
  Raumhöhe im Bericht nicht.
- Ecken und Kanten aus 1–3 m Abstand aufnehmen. Spiegel, Fenster und Glas
  liefern keine LiDAR-Tiefe.
- Gleichmäßiges Licht, keine Personen im Bild.

**Optional: hochaufgelöste Fotos (deutlich schärferer Splat)**
- Normale Kamera-App, gleicher Raum, kurz nach dem Scan.
- 100–300 Fotos, 60–80 % Überlappung, mehrere Höhen, Details zusätzlich von nah.
- Belichtung und Weißabgleich fixieren (z. B. Lightroom Mobile, ProCamera);
  kein HDR, keine Bewegungsunschärfe.
- JPG oder HEIC. HEIC braucht `pillow-heif`; das Pod-Skript installiert es selbst.
- **Nicht** vorher mit KI hochrechnen oder nachschärfen: Jedes Bild bekäme andere
  „erfundene" Details, und der Splat bildet daraus Flimmern und Schweber.

### Ohne eigenen Scan: freie iPad-Daten (ARKitScenes)

Apple hat mit **ARKitScenes** über 5.000 echte iPad-Pro-Aufnahmen von Innenräumen
veröffentlicht: Farbbilder, LiDAR-Tiefe mit Konfidenz und ARKit-Posen. Für rund
2.200 davon gibt es zusätzlich die Tiefe aus einem **Faro-Laserscanner** als
Referenz. Damit lässt sich die Pipeline an echten Daten erproben, und der Bericht
zeigt, wie genau das iPad-LiDAR in diesem Raum wirklich war
(`lidar_vs_laserscanner`: Median- und 90-%-Fehler in cm).

```bash
bash scripts/arkitscenes_fetch.sh 41069021          # ein Raum, grob 0,5–2 GB (geschätzt)
python scripts/ipad_capture.py prepare arkitscenes_41069021 raum_daten
# oder gleich mit Splat-Training auf der GPU:
bash scripts/train_ipad_runpod.sh arkitscenes_41069021
```

Andere Räume: eine `video_id` aus
[upsampling_train_val_splits.csv](https://github.com/apple/ARKitScenes/blob/main/depth_upsampling/upsampling_train_val_splits.csv)
wählen (mit Laserscanner-Referenz und 1920×1440-Bildern).
**Lizenz:** nur nicht-kommerzielle Nutzung, Quelle nennen (Baruch et al.,
ARKitScenes, NeurIPS 2021). Die Ergebnisse daher nicht ohne Prüfung öffentlich in
die Galerie stellen.

Ebenfalls frei, aber noch ohne Leser: **MuSHRoom** (iPhone + Kinect +
Faro-Referenz, Zenodo) und **ScanNet++** (iPhone + DSLR + Laserscanner,
Registrierung nötig).

## 2. Verarbeitung: ein Befehl auf einer Miet-GPU

Scan (und optional Fotos) als ZIP irgendwo per Link ablegen. Auf einem
RunPod-Pod (CUDA-*devel*-Vorlage, ≥16 GB VRAM) dann:

```bash
export CAPTURE_URL="https://…/scan.zip"
export STILLS_URL="https://…/fotos.zip"      # optional
curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_ipad_runpod.sh | bash
```

Liegen die Dateien schon auf dem Pod:
`bash train_ipad_runpod.sh /workspace/scan.zip /workspace/fotos.zip`.
Fotos dürfen auch im Scan-ZIP unter `stills/` liegen.

Am Ende stehen eine Download-URL und die Raummaße. Dauer für einen Raum mit
~300 Keyframes: ca. 20–40 min Training, mit Fotos plus COLMAP-Zeit auf der CPU.
Stellschrauben stehen im Kopf von [train_ipad_runpod.sh](scripts/train_ipad_runpod.sh)
(`STEPS`, `MAX_FRAMES`, `FACTOR`, `DEPTH_LAMBDA`, `POSE_OPT` …).

Lokal (CUDA-Workstation) funktioniert dasselbe Skript aus dem Repo-Checkout:
`bash scripts/train_ipad_runpod.sh scan.zip fotos.zip`.

### Nur vermessen, ohne GPU

Die Messwolke und die Raummaße entstehen schon im ersten Schritt, auf jedem Rechner:

```bash
pip install numpy pillow
python scripts/ipad_capture.py prepare <entpackter-export> raum_daten
# -> raum_daten/lidar_points.ply, raum_daten/capture_report.json
```

## 3. Messen

**CloudCompare** (kostenlos): `raum_lidar_points.ply` öffnen, dann das Werkzeug
*Point picking* („Punkte auswählen") und zwei Punkte anklicken. Die Strecke wird
in Metern angezeigt. Für Wandabstände besser eine Ebene je Wand einpassen
(*Tools → Fit → Plane*) und die Ebenenabstände ablesen; das mittelt das
LiDAR-Rauschen heraus.

**Bericht:** `raummasse_naeherung` sind die Hüllmaße der Wolke (0,5–99,5 %
Perzentil, Grundriss als kleinstes gedrehtes Rechteck). Das ist eine schnelle
Kontrolle, kein Aufmaß. Nischen, Erker und schräge Wände sind darin nicht
abgebildet.

## 4. In der Galerie zeigen

```bash
python platform/dev/seed_splat.py raum_splat.ply --id mein-raum \
    --title "Mein Raum" --camera-up 0 1 0 --metric
```

`--metric` schaltet im Splat-Viewer das Werkzeug **📏 Messen** frei: zwei Punkte
anklicken, die Strecke steht in Metern daneben. Außerdem startet die Ansicht in
Augenhöhe mitten im Raum. Große Dateien extern hosten (`--external-url`, siehe
[docker/README.md](docker/README.md)).

## 5. Was technisch passiert

```
App-Export ──► ipad_capture.py prepare
               ├─ Keyframes (Bewegungsfenster, je Fenster das schärfste Bild)
               ├─ ARKit-Posen → COLMAP-Modell (keine SfM nötig, metrisch)
               ├─ LiDAR-Tiefe (nur hohe Konfidenz, ohne Kanten-Pixel) → Weltpunkte
               │    als points3D mit Track auf „ihr" Bild
               └─ Messwolke + Raummaße
Fotos? ──────► ipad_sfm.sh
               ├─ SIFT + Matching (COLMAP)
               ├─ point_triangulator mit FESTEN ARKit-Posen → metrische Merkmale
               ├─ image_registrator: Fotos per PnP → Fotoposen in Metern
               └─ ipad_capture.py refine: Kontrolle (Maßstab ≈ 1) + LiDAR-Tiefe
                    auch für die Fotos (Sichtbarkeit per Z-Puffer)
gsplat ──────► Start auf den LiDAR-Punkten, --depth_loss (LiDAR-Tiefe als Prior),
               --pose_opt (gleicht ARKit-Drift fein aus)
Export ──────► gsplat_export_metric.py rechnet die gsplat-Normalisierung heraus
               (Position, Größe, Drehung und Blickabhängigkeit/SH) → Meter
```

**Warum kein freies SfM über alle Bilder?** Freie Rekonstruktionen driften im
Maßstab, in Räumen mit vielen Drehungen und kurzen Wegen besonders stark. Im
synthetischen Test sprang eine freie COLMAP-Rekonstruktion an zwei Stellen,
und keine einzelne Ähnlichkeitstransformation passte mehr (RMS 27 cm). Mit
festen ARKit-Posen und PnP-Einhängung landen die Fotos dagegen im Testraum auf
etwa 1 mm und 0,05° genau. Die Kontrolle in `refine` bricht ab, wenn die
Ausrichtung schlechter als 8 cm ist. Dann wird nur mit den ARKit-Frames
trainiert, statt mit falschen Fotoposen.

## 6. Grenzen

- **Reichweite** ca. 5 m: kleine bis mittlere Räume. Für Hallen, Fassaden und Wald
  ist ein Rundum-LiDAR (z. B. Livox Mid-360 mit FAST-LIVO2) der nächste Schritt.
  Die Splat-Pipeline ab „gsplat" bleibt dieselbe.
- **ARKit-Drift** über lange Wege: im kleinen Raum vernachlässigbar, in großen
  Räumen den Weg in einer Schleife zum Start zurückführen.
- **Glas, Spiegel, schwarze und glänzende Flächen:** keine oder falsche Tiefe.
  Der Splat sieht dort gut aus, ist aber nicht metrisch abgesichert.
- **Getestet** sind die Pipeline-Schritte an einem synthetischen Raum mit
  bekannter Geometrie (`tests/test_ipad_pipeline.py`, `tests/synth_room.py`):
  Posen, Rückprojektion, COLMAP-Ausgabe, Foto-Einhängung (auch mit echtem COLMAP
  3.9), metrischer Export durch den gsplat-Parser und das 📏-Werkzeug im Browser.
  Der ARKitScenes-Leser ist an einem synthetischen Datensatz im ARKitScenes-Layout
  geprüft (Posen-Interpolation, Tiefe zu anderem Zeitpunkt, Referenzvergleich).
  Ein Download war aus der Entwicklungsumgebung heraus nicht möglich.
  Die App-Leser folgen den dokumentierten Exportformaten. Bei der ersten echten
  Aufnahme lohnt ein Blick in `capture_report.json` (Frames, Punkte, Raummaße).
  Wird ein Export nicht erkannt, hilft eine Dateiliste des ZIPs bei der Anpassung.

## Werkzeuge

| Skript | Aufgabe |
|---|---|
| [scripts/ipad_capture.py](scripts/ipad_capture.py) | `prepare` / `known` / `refine` (numpy + Pillow) |
| [scripts/ipad_sfm.sh](scripts/ipad_sfm.sh) | Fotos metrisch einhängen (COLMAP) |
| [scripts/arkitscenes_fetch.sh](scripts/arkitscenes_fetch.sh) | freie iPad-Testdaten (Apple ARKitScenes) holen |
| [scripts/gsplat_export_metric.py](scripts/gsplat_export_metric.py) | gsplat-Checkpoint → .ply in Metern |
| [scripts/train_ipad_runpod.sh](scripts/train_ipad_runpod.sh) | alles in einem Befehl auf der GPU |
| [platform/dev/seed_splat.py](platform/dev/seed_splat.py) `--metric` | in die Galerie, mit 📏 Messen |
