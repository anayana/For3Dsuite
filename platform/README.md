# 360Pano3D Platform — Self-Hosting-Stack

Selbst gehostete Open-Source-Plattform, die Fotos und terrestrische Laserscans zu
interaktiven 360°-Szenen verarbeitet und veröffentlicht. Marker in den Panoramen
verorten aus der Punktwolke abgeleitete Inventurdaten (z. B. Baumart, BHD, Höhe)
und zeigen sie per Klick in Infoboxen.

```
                 ┌──────────── Caddy (TLS, Routing, Basic-Auth) ────────────┐
                 │                                                          │
  /admin  ────►  Studio-UI   (Upload, Job-Status, Marker-Editor)  [Login]   │
  /       ────►  Gallery-UI  (Szenenauswahl → Pannellum-Viewer)  [öffentl.] │
  /media  ────►  Garage-Web-Endpoint (Bucket "media")                       │
                 │                                                          │
                 ▼                                                          │
        App (FastAPI + Worker-Thread + SQLite-Queue)                        │
          • equirect: fertiges Panorama übernehmen                          │
          • fisheye:  Hugin-CLI (pto_gen → cpfind → … → nona → enblend)     │
          • e57:      Pinhole-Bilder + Posen extrahieren → Reprojektion     │
                 │                                                          │
                 ▼                                                          │
        Garage (S3): Bucket "originals" (privat) · Bucket "media" (öffentl.)
```

## Schnellstart: lokale Entwicklung (ohne Docker)

```powershell
pip install fastapi "uvicorn[standard]" python-multipart pillow numpy
python platform\dev\seed_demo.py                 # Demo-Szenen aus output/ übernehmen
python -m uvicorn main:app --port 8361 --app-dir platform\app
```

Dann: Gallery unter `http://localhost:8361/`, Studio unter `http://localhost:8361/admin/`.
Medien und Job-Datenbank liegen unter `platform/dev-data/` (Storage-Backend `local`).
Optional `STUDIO_PASSWORD` (und `STUDIO_USER`) setzen, um das Studio auch lokal zu schützen.

## Produktion: Docker auf eigenem Server

Voraussetzungen: Linux-Server mit Docker + Compose, eine Domain, deren A/AAAA-Record
auf den Server zeigt (Caddy holt TLS-Zertifikate automatisch).

```bash
cd platform
cp .env.example .env            # DOMAIN, STUDIO_USER eintragen
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'MEIN-PASSWORT'
                                # → Hash in .env als STUDIO_HASH ($ als $$ escapen)
bash init/bootstrap.sh          # Garage: Layout, Buckets, App-Key (einmalig)
                                # → ausgegebene S3-Keys in .env eintragen
docker compose up -d --build
```

- `bootstrap.sh` generiert das Garage-`rpc_secret`, legt die Buckets `media`
  (öffentlich, Web-Endpoint) und `originals` (privat) an und erzeugt den
  S3-Schlüssel `pano-app` für die App.
- Caddy schützt `/admin` und `/api/studio` per Basic-Auth und bedient `/media/*`
  direkt aus Garage — Panorama-Downloads laufen nicht durch die Python-App.
- Lokaler Test ohne Domain: `DOMAIN=:80` in `.env`, dann `http://localhost/`.

## Datenmodell

Pro Szene liegt ein Manifest `scenes/<id>/scene.json` im Media-Bucket:

```json
{
  "id": "renon-setup01",
  "title": "Renon / ICOS IT-Ren — Setup 01",
  "pano": "scenes/renon-setup01/pano.jpg",
  "thumb": "scenes/renon-setup01/thumb.jpg",
  "width": 8192, "height": 4096,
  "source": { "type": "e57", "origin_xyz": [31.803, -4.557, 3.858] },
  "pointcloud": { "bin": "scenes/renon-setup01/cloud.bin", "count": 700000,
                  "stride": 15, "bbox_min": [...], "bbox_max": [...] },
  "markers": [
    { "id": "t001", "label": "Baum 01", "yaw": 71.5, "pitch": -11.0,
      "xyz": [34.96, 4.89, 1.93],
      "attributes": { "BHD_cm": 75.8, "Hoehe_m": 26.8, "Distanz_m": 10.15 },
      "demo": false }
  ]
}
```

`source.origin_xyz` ist der Scan-Ursprung (Kamera-Translation aus der E57-Pose) im
Punktwolken-Koordinatensystem. `pointcloud` (optional) verweist auf die kompakte
Web-Punktwolke für die 3D-Ansicht. Bei Neu-Verarbeitung einer Szene bleiben
vorhandene Marker erhalten.

## Zwei Ansichten pro Szene: Panorama ⇄ 3D-Punktwolke

Der Szenen-Viewer bietet oben einen Umschalter **Panorama | 3D-Punktwolke**. Die
3D-Ansicht (Three.js, [cloudviewer.js](web/gallery/cloudviewer.js)) lädt eine
kompakte Binärdatei (Blockformat: float32-XYZ-Block + uint8-RGB-Block, zero-copy
im Browser) aus [pointcloud_web.py](../scripts/pointcloud_web.py) — auf den
Scan-Ursprung zentriert, in **zwei Dichte-Stufen** (`pointcloud.levels`):
„Ausgedünnt" (~160 k Punkte / 2 MB, Default für schnellen Erstaufruf) und „Voll"
(~700 k / 10 MB), im Viewer unten umschaltbar. Zusätzlich erzeugt jeder Job
**drei Farbstufen** des Panoramas (`variants`: Natur/Kräftig/Hell, via
[pano_variants.py](../scripts/pano_variants.py), Pillow statt GIMP) mit
Umschaltleiste im Panorama-Modus; die Blickrichtung bleibt beim Wechsel erhalten.
**Dieselben Marker** erscheinen in beiden
Ansichten (im Panorama als Yaw/Pitch-Hotspot, in 3D als Billboard an der
XYZ-Position) und öffnen dieselbe Infobox. Für den E57-Job erzeugt der Worker die
Web-Punktwolke automatisch mit.

Für **sehr große Clouds** (mehrere Setups, >10 M Punkte) skaliert dieses
Single-File-Format nicht; dann PotreeConverter (LOD-Octree) im Worker vorziehen und
den Potree-Viewer statt cloudviewer.js einbinden — das Datenmodell (`pointcloud`)
ist dafür offen.

## Marker aus Punktwolken-Inventuren

Weil E57-Dateien die Kamera-Pose im Punktwolken-Koordinatensystem mitliefern, lassen
sich Objektpositionen aus der Wolke exakt in Panorama-Blickwinkel umrechnen
(Konvention wie `scripts/reproject_pano.py`):

```
yaw = atan2(dy, dx)     pitch = asin(dz / |d|)     mit d = P_objekt − P_ursprung
```

Zwei Wege zu den Einzelbaumdaten:

1. **Mitgelieferte Baseline** ([inventory_from_cloud.py](../scripts/inventory_from_cloud.py),
   nur numpy): Bodenmodell → Brusthöhen-Scheibe (1,0–1,6 m) → Clusterung →
   Kasa-Kreis-Fit je Stamm → Position + BHD, Höhe aus dem lokalen Maximum.
   ```powershell
   python scripts\inventory_from_cloud.py scan.e57 trees.csv --origin X Y Z --radius 18
   ```
   Am ICOS-Renon-Setup 001 findet sie 87 Stämme (BHD 8–76 cm). Als Baseline
   gedacht; für publikationsreife Genauigkeit gegen lidR/TreeLS oder 3DFin
   vergleichen und an einer Referenzinventur validieren.
2. Externe Ableitung (lidR/TreeLS in R, 3DFin in Python) → CSV mit Spalten
   `x,y,z,label,<Attribute…>`.

Dann die Positionen in Marker umrechnen und ins Manifest schreiben:

```powershell
python scripts\markers_from_xyz.py trees.csv --scene pfad\zu\scene.json
```

alternativ `--origin X Y Z` und `--out markers.json`. Feinjustierung danach im
Studio-Marker-Editor (Klick ins Panorama setzt neue Marker, Attribute als JSON
editierbar).

## API-Kurzreferenz

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/scenes` | Szenenliste (öffentlich) |
| GET | `/api/scenes/{id}` | Szenen-Manifest inkl. `pano_url` |
| POST | `/api/studio/upload` | Multipart: `scene_id`, `type` (equirect/fisheye/e57), `title`, `fov`, `lens`, `files[]` |
| GET | `/api/studio/jobs[/{id}]` | Job-Status + Log |
| PUT | `/api/studio/scenes/{id}/markers` | Marker ersetzen |
| PATCH | `/api/studio/scenes/{id}` | Titel/Beschreibung ändern |
| DELETE | `/api/studio/scenes/{id}` | Szene entfernen |

## Grenzen / Roadmap

- **3D-Viewer skaliert nicht für sehr große Clouds:** das Single-File-Format
  (~700 k Punkte, kein LOD) genügt pro Setup, nicht für ganze Kampagnen. Für
  Multi-Setup-Touren PotreeConverter (LOD-Octree) im Worker vorziehen.
- **Inventur-Baseline ist bewusst einfach:** `inventory_from_cloud.py` (numpy-only,
  Kreis-Fit) hat systematische Fehler an Hängen und bei Teilbogen-Sicht (einige
  Ausreißer in Höhe/Position). Vor Publikation gegen lidR/TreeLS bzw. 3DFin und eine
  Referenzinventur validieren.
- **Baumart** wird nicht automatisch bestimmt (am Renon-Standort quasi-Reinbestand
  *Picea abies*); Attribut manuell oder aus externer Quelle setzen.
- **Automatische Inventur läuft noch nicht im Worker:** der Upload erzeugt Panorama +
  Web-Punktwolke, die Stammerkennung ist derzeit ein separater CLI-Schritt.
- **Pannellum/Multires:** sehr große Panoramen (>8192 px) sollten getilt werden
  (`scripts/tile_pano.ps1`); der Worker skaliert derzeit nicht automatisch herunter.
- **CDN-Abhängigkeit:** Pannellum und Three.js kommen von jsdelivr. Für strikt offline
  betriebene Server die Dateien lokal ablegen und die URLs/Importmap in
  `platform/web/gallery/*.html` anpassen.
- **Publikation:** Zielformat Software-/Methoden-Paper mit Anwendungsfall
  ICOS-Renon (Validierung der abgeleiteten Inventurwerte gegen Referenzmessungen).
