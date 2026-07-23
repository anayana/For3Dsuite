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
python platform\dev\seed_polyhaven.py            # 8 CC0-Wald-Panoramen von Poly Haven (API-Download)
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

**Wolken-only-Szenen:** Ist `pano` null (Laserscan ohne Bilder, z. B. TreeScope),
startet der Viewer direkt in der 3D-Ansicht, der Panorama-Umschalter entfällt und
die Wolke wird per Höhen-Farbverlauf eingefärbt (kein RGB). Trägt die Szene einen
`validation`-Block (Recall/Precision/Lagefehler gegen Datensatz-Ground-Truth), wird
er unten links eingeblendet.

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
   nur numpy): Bodenmodell → Detektionsband → Clusterung → Kasa-Kreis-Fit je Stamm.
   Berechnet je Baum **BHD** (schmales Messfenster um 1,3 m, verjüngungsarm),
   **Grundfläche** = π·(BHD/2)², sowie **Höhe** und **Schaftvolumen**
   (= Grundfläche·Höhe·Formfaktor), letztere nur wenn die Wolke die Krone erfasst;
   bei gekappten Low-Scans wird die Höhe ehrlich als „erfasst" markiert statt als
   Baumhöhe ausgegeben. Detektions-Schwellen sind per CLI einstellbar (dichte TLS
   vs. dünne Mobile-Scans):
   ```powershell
   # dichte stationäre TLS (Renon E57):
   python scripts\inventory_from_cloud.py scan.e57 trees.csv --origin X Y Z --radius 18
   # dünner mobiler Scan (TreeScope PCD):
   python scripts\inventory_from_cloud.py scan.pcd trees.csv `
       --min-points 15 --arc-min 50 --rms-max 5 --bh 0.5 2.5
   ```
   Renon-Setup 001: 87 Stämme (BHD 8–76 cm). Baseline; für höhere Genauigkeit
   gegen lidR/TreeLS oder 3DFin vergleichen.
2. Externe Ableitung (lidR/TreeLS in R, 3DFin in Python) → CSV mit Spalten
   `x,y,z,label,<Attribute…>`.

### Validierung gegen Ground-Truth (TreeScope)

Der **TreeScope**-Datensatz (tnl.treescope.org, mobiler Wald-Laserscan mit
Per-Punkt-Instanz-Labels) liefert eine echte Referenz, gegen die die berechnete
Erkennung geprüft wird — der publikationsrelevante Schritt „Werte wirklich
berechnet **und** validiert" statt Augenschein:

```powershell
Rscript scripts\download_treescope.R 0 5                 # Kacheln laden
python scripts\validate_treescope.py cloud1_0_all_points.pcd `
    cloud1_0_all_points.labels cloud1_0_trees.csv --match-dist 0.5 --min-gt-points 20
```

liefert Recall / Precision / F1 + Lagefehler (Greedy-Nearest-Matching gegen die
GT-Positionen aus den Instanz-Labels). Baseline auf WSF-19/Kachel 0:
**Recall 91 %, Precision 72 %, Lagefehler 9 cm (Median)** bei 69 Referenzbäumen.
[seed_treescope.py](dev/seed_treescope.py) spielt die Kachel als reine
Punktwolken-Szene ein (Inventur → Validierung → Web-Wolke → Marker); die Kennzahlen
landen im Manifest (`scene.validation`) und werden im Viewer eingeblendet.

### SYSSIFOSS — Blatt-Holz-getrennte Einzelbäume

Der **SYSSIFOSS**-Datensatz (heiDATA [doi:10.11588/DATA/UUMEDI](https://doi.org/10.11588/DATA/UUMEDI),
CC-BY-4.0, RIEGL VZ-400) liefert elf manuell blatt-/holz-separierte Einzelbäume aus
den Waldplots bei Bretten und Karlsruhe — die `classification` im LAZ ist damit
**Ground Truth statt Schätzung** (0 = Holz, 1 = Blatt).
[seed_syssifoss.py](dev/seed_syssifoss.py) baut daraus drei Szenen:

```powershell
python platform\dev\seed_syssifoss.py            # alle drei
```

| Szene | Inhalt | Lage |
|---|---|---|
| `syssifoss-br01` | Rotbuche + Traubeneiche | **echt** (EPSG:25832, 50 m Abstand, 12,6 m Höhenversatz) |
| `syssifoss-ka09` | Waldkiefer + Roteiche | **echt** (32 m Abstand) |
| `syssifoss-arboretum` | alle 11 Bäume, 6 Arten | **synthetisch** im 16-m-Raster (Originalstandorte ~20 km auseinander) |

Zwei Fallstricke, die dabei teuer waren:

- **float32 reicht für UTM nicht.** Bei Rechtswerten um 5,4·10⁶ bleiben in float32
  keine 0,5 m Auflösung — der Stammquerschnitt wird zum Quantisierungsraster und
  der BHD-Fit zu Rauschen. Erst nach Abzug des Szenen-Ursprungs auf float32 gehen.
- **Der BHD-Ring braucht eine Einschnürung.** Die Wolken sind aus dem Plotscan
  ausgeschnitten, im Brusthöhenring liegen also auch Nachbarstämme. Ein Kreis-Fit
  über alles liefert Radien im Kilometerbereich; der Fit läuft daher iterativ vom
  dichtesten Stammpixel aus und zieht den Fangradius je Runde auf das 1,35-fache
  des aktuellen Stammradius. Erst damit werden die Werte plausibel (Douglasie
  47,3 m / 84,8 cm, junge Roteiche 10,8 m / 8,8 cm) — vorher stand dieselbe
  Roteiche mit 110 cm da.

Dann die Positionen in Marker umrechnen und ins Manifest schreiben:

```powershell
python scripts\markers_from_xyz.py trees.csv --scene pfad\zu\scene.json
```

alternativ `--origin X Y Z` und `--out markers.json`. Feinjustierung danach im
Studio-Marker-Editor (Klick ins Panorama setzt neue Marker, Attribute als JSON
editierbar).

## Hedge Vertical Index aus offenem ALS

[seed_hvi_ahn.py](dev/seed_hvi_ahn.py) + [hvi_ahn_scene.R](dev/hvi_ahn_scene.R)
bringen den HVI aus dem Nachbarrepo `shrub_div` auf eine offene ALS-Kachel
(AHN, Niederlande, ~21 Pkt/m², CC-BY-4.0) und machen daraus eine Szene:
**214 Heckensegmente auf 1 km², HVI 0,17–0,80**. Heckenpunkte tragen die Farbe
ihres Indexwerts, Boden und Umfeld bleiben gedämpft — der Index wird damit im
begehbaren Raum sichtbar, nicht nur in der Tabelle.

```powershell
python platform\dev\seed_hvi_ahn.py            # rechnet und baut
python platform\dev\seed_hvi_ahn.py --skip-r   # nur neu paketieren
```

Der Index verhält sich plausibel: Segment mit HVI 0,80 hat 5 Schichten,
FHD 2,31 und 6,3 m Höhe; das schwächste (0,17) 2 Schichten, FHD 0,70, 1,4 m.

Vier Dinge, die dabei zu klären waren:

- **`hvi_ahn_hedges()` aus shrub_div ist für Netze unbrauchbar.** Es verwirft
  Polygone über 1500 m², ein zusammenhängendes Heckennetz *ist* aber genau ein
  großes Polygon — im ersten Test blieben 2 Fragmente von 86 Netzteilen übrig.
  Ersetzt durch: Schmalheitstest (Fläche/Umfang ≈ halbe Streifenbreite, hier
  1,7 m — längenunabhängig, trennt Hecke von Waldblock), danach Schnitt mit
  einem 20-m-Raster. 20 m ist die übliche Erhebungseinheit in Heckenkartierungen
  und liefert genug Segmente, damit die *relative* HVI-Normierung überhaupt trägt.
- **`cover_frac` ist konstant 1,00** über alle 214 Segmente und trägt damit
  nichts bei — die Segmente werden aus der Vegetationsmaske abgeleitet, also ist
  die Deckung darin zwangsläufig vollständig. Der Subindex Volumen/Größe
  schrumpft faktisch auf die Höhe. Mit *kartierten* Polygonen (UKCEH für
  England) würde `cover_frac` Lücken in der Heckenlinie messen und wieder
  Information tragen — das ist das stärkste Argument für den lizenzierten Layer.
- **Der HVI ist relativ**, nicht absolut: `hvi_rescale()` normiert auf das
  2.–98.-Perzentil *dieses Ausschnitts*. Werte aus zwei Ländern sind ohne
  gemeinsame Referenz nicht vergleichbar.

### Arteignung: umschaltbare Einfärbung

Neben dem HVI leitet `hvi_species_suitability()` je Segment die Habitateignung
für fünf Zielarten ab (gewichtetes Fuzzy-Mittel aus Antwortkurven je Kennwert,
`species_requirements.csv`). Die Punktwolke trägt eine **Segment-ID-Spur**
(uint16, dritter Block im `.bin` nach xyz und rgb), sodass der Viewer über einen
Dropdown live zwischen HVI-Struktur und jeder Art umfärbt — ohne weitere
Downloads. Jeder Marker führt die fünf Eignungswerte plus die beste Art im Klartext.

> Ein Marker-Bug fiel dabei auf: die Eignung wurde berechnet, aber nie
> angezeigt — der Sammel-Filter suchte Spalten mit Präfix `HSI`, die R-Ausgabe
> benennt sie aber nach der Art. Jetzt über die Artenliste nachgeschlagen.

Was die Einfärbung an diesem 1-km²-Ausschnitt zeigt, ist ökologisch stimmig und
ehrlich: das Gebiet ist von **hohen, durchgehenden Hecken** geprägt
(Median h_p95 ≈ 6,7 m). Das macht es zu erstklassigem **Fledermaus-Leitraum**
(Eignung Median 0,99, 203 von 214 Segmenten > 0,5), aber zu schlechtem Habitat
für Sträucher-Vögel, die 1,5–3 m hohe Hecken brauchen: Neuntöter (20 Segmente),
Dorngrasmücke (8), Goldammer (0). Die Wildbienen-Kurve bleibt zusätzlich flach,
weil sie NDVI verlangt — das fehlt ohne Spektralraster. Zwei der fünf Arten
färben also fast einheitlich; das ist eine Aussage über die Landschaft, kein
Fehler. Die Antwortkurven selbst sind unkalibrierte Startwerte.
- **Nicht die ganze Kachel einlesen.** `hvi_ahn_run()` liest erst alles und
  schneidet dann zu — bei 340 Mio. Punkten unmöglich. Der `-keep_xy`-Filter
  greift beim Lesen; er muss die Kachel trotzdem komplett dekomprimieren (~6 min,
  unabhängig von der Fenstergröße), deshalb wird die normalisierte Wolke
  zwischengespeichert.

## Kronenanalyse: LAI auf zwei unabhängigen Wegen

[canopy_lai.py](../scripts/canopy_lai.py) + [canopy_lai.R](../scripts/canopy_lai.R)
rechnen für **denselben Standpunkt** beide in der Forstpraxis üblichen
Schätzungen — das geht nur, weil eine E57-Szene Panorama *und* Punktwolke aus
einer Aufnahme liefert:

```powershell
python scripts\canopy_lai.py platform\dev-data\media\scenes\renon-setup01 `
    --e57 "data\Renon\e57\Renon cp2- Setup 001.e57"
```

| Weg | Kette | Ergebnis Renon Setup 01 |
|---|---|---|
| optisch | Panorama → äquidistantes Zenit-Fisheye ([hemi_from_pano.py](../scripts/hemi_from_pano.py)) → `hemispheR` | LAI **1,56** (effektiv 1,41, Clumping 0,90), Himmelsanteil 36,6 % |
| strukturell | E57 → LAS → `lidR`: CSF-Bodenklassifikation, TIN-Normalisierung, `LAD()` (MacArthur-Horn, 1-m-Schichten ab 2 m) | LAI **3,64**, Bestandeshöhe P95 16,7 m |

**Das ist kein Validierungspaar, und die Differenz ist der Punkt.** Beide Wege
haben gegenläufige Verzerrungen: das Panorama ist aus Scanner-Pinhole-Bildern
reprojiziert (keine Fisheye-Optik) und bei überstrahltem Himmel wird helles
Nadelwerk als Lücke gezählt — LAI zu niedrig. MacArthur-Horn wiederum unterstellt
senkrechte Durchdringung wie bei ALS, angewandt auf einen *einzelnen*
terrestrischen Standpunkt zieht Verdeckung hinter Stämmen den Wert nach unten.
Der Viewer zeigt deshalb beide Zahlen samt Vorbehalt nebeneinander, nicht eine
gemittelte „Wahrheit".

Eine Stellschraube ist dabei keine: `gamma = 2.2` linearisiert das sRGB-JPG. Mit
`gamma = 1` setzt Otsu die Schwelle bei 138 statt 107 und der LAI fällt um ein
Drittel auf 1,04 — der Wert folgt aus der Kodierung der Datei, nicht aus einer
Vorliebe. Die Auswertung läuft auf dem verlustfreien `hemi.png`; die `hemi.jpg`
daneben ist nur die Anzeigekopie (JPEG-Artefakte würden die Otsu-Schwelle
verschieben).

> `leafR` wäre die naheliegende Wahl für den strukturellen Weg, ist aber auf CRAN
> archiviert und unter R 4.4 nicht installierbar. `lidR` bringt `LAD()` und
> `gap_fraction_profile()` selbst mit — dieselbe Methode aus dem gepflegten Paket.

## Freilauf im 3D-Viewer

Punktwolken-Szenen haben oben rechts zwei Navigationsarten:

- **Umkreisen** — Orbit um die Wolke (Standard, funktioniert auch auf Touch).
- **Begehen** — First-Person mit Pointer-Lock: <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd>
  gehen, Maus umsehen, <kbd>Leertaste</kbd>/<kbd>C</kbd> höher/tiefer,
  <kbd>Shift</kbd> dreifaches Tempo, <kbd>Esc</kbd> beendet. Klick auf einen Baum
  öffnet dessen Kennwerte (der Zeiger wird dafür freigegeben). Damit bewegt man
  sich **stufenlos durch den Bestand**, statt von Standpunkt zu Standpunkt zu
  springen.

Zwei Umsetzungsdetails in [cloudviewer.js](web/gallery/cloudviewer.js):

- Three.js' `PointerLockControls` ist **nicht verwendbar**: es rechnet mit
  YXZ-Euler und setzt damit Y = oben voraus, die Szene ist aber (wie das E57)
  Z-oben. Yaw/Pitch werden deshalb selbst geführt und per `lookAt` angewandt.
- Vorwärts bleibt **waagerecht**, auch beim Hochschauen — Höhe ausschließlich über
  <kbd>Leertaste</kbd>/<kbd>C</kbd>. Das läuft sich deutlich vorhersehbarer als
  echtes Fliegen, wenn man in einer Wolke ohne Kollisionsgeometrie unterwegs ist.
  Ein Bodenraster nach Größe der Wolke gibt dabei die einzige verlässliche
  Höhen- und Richtungsreferenz.

## Was öffentlich geht: publish.json

[publish.json](dev/publish.json) kuratiert den statischen Export. Leitlinie: **je
Methode/Datensatz/Anwendung genau ein Beispiel** — 19 gebaute Szenen, 10 online,
`docs/` dadurch von 198 auf 126 MB.

Ausnahme von der Ein-Beispiel-Regel sind die CC0-Panoramen: davon bleiben **vier**
online, je eines pro Region, damit die Übersichtskarte nicht auf einen Punkt
zusammenfällt — Dublin (53,3 °N), Sachsen (51,0 °N), Gauteng (−26,2 °S) und
KwaZulu-Natal (−29,0 °S), zusammen 82 Breitengrade.

Zurückgehalten werden Dubletten: 7 Poly-Haven-Panoramen, die eine dieser Regionen
doppeln oder gar keine Koordinate tragen, `hedgerow-be-birch` (gleiche Auswertung
wie `-alder`) und `syssifoss-ka09` (gleiche Auswertung wie `-br01`).

Nichts davon wird gelöscht: `platform/dev-data/` behält alle Szenen, die lokale
Gallery zeigt sie weiter, und die Seed-Skripte bauen jede jederzeit neu. Eine
Szene wieder online stellen = Zeile in `publish.json` ergänzen, `export_static.py`
laufen lassen. Fehlt die Datei, exportiert das Skript wie früher alles.

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

## Qualität & Wachstum (Bausteine 4 & 5)

Über die reine Inventur hinaus (Konzept: [BAUSTEINE_4_5_1.md](../BAUSTEINE_4_5_1.md)):

- **Qualitative RGB-Attribute je Baum** ([qualitative_rgb.py](../scripts/qualitative_rgb.py)):
  Farbindizes (ExG/GLI), GLCM-Textur und ein bestandesrelativer Vitalitätsproxy
  aus einem reprojizierten Kronen-Crop — georeferenziert in die Marker-Attribute
  der `scene.json`, im Viewer in derselben Infobox sichtbar. Gegenprobe gegen die
  Struktur: [crossvalidate_rgb_lidar.py](../scripts/crossvalidate_rgb_lidar.py).
- **Wachstumsprognose** ([growth-service/](../growth-service/README.md)):
  TreeGrOSS/BWINPro als isolierter Java-Dienst (GPLv3), angebunden über
  [treegross_export.py](../scripts/treegross_export.py). Zukunftsbestände fließen
  als aktualisierte `scene.json` zurück — derselbe Viewer, prognostizierter Wald.
  Baumart (Attribut `Art`, Default `Picea abies` am Renon-Reinbestand) steuert das
  Artcode-Mapping; noch nicht automatisch bestimmt.
