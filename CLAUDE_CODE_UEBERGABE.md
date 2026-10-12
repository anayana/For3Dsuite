# Übergabe an Claude Code — For3Dsuite: Studio-GUI + Medien-Marker

Stand: 12.10.2026 · Repo: `anayana/for3dsuite` · geprüfter Commit: `7886ba3` (05.10.2026)

Diese Datei ins Repo-Wurzelverzeichnis legen und Claude Code als Erstes lesen lassen.
Zugehöriges Konzept: `Paper_ODT/Heritage_Toolkit_Paper/Heritage_Toolkit_Konzept.md`
(Paper B „Memory Twin Toolkit“).

---

## 0. ACHTUNG bei Arbeit in der Cloud (Handy / claude.ai/code)

`platform/dev-data/` (die eigentlichen Szenendaten mit Markern und Medien) ist
**nicht in Git** (`.gitignore`) und liegt nur auf dem Notebook.
`export_static.py` löscht `docs/` komplett und baut es aus `platform/dev-data/` neu.
**In der Cloud würde ein Export deshalb die gesamte Galerie inkl. aller Marker löschen.**

- In der Cloud **niemals** `platform/dev/export_static.py` ohne Schutz ausführen.
- Erste Aufgabe: `export_static.py` um einen Modus `--html-only` erweitern, der nur
  HTML/JS aus `platform/web/gallery/` nach `docs/` patcht/kopiert und `docs/data/` +
  `docs/media/` unangetastet lässt. Ohne `platform/dev-data/` soll das Skript mit
  Fehler abbrechen statt `docs/` zu löschen.
- Marker-Daten in der Cloud nur in `docs/data/*.json` ändern; diese Änderungen
  müssen später auf dem Notebook nach `platform/dev-data/media/scenes/*/scene.json`
  zurückgespielt werden (Skript dafür anlegen), sonst überschreibt der nächste
  Notebook-Export sie.

---

## 1. Ziel

Eine **nutzerfreundliche GUI**, mit der Laien selbstständig:

1. **Rohdaten hochladen** (Fotos, 360°-Bilder, E57, später Bildserien für 3DGS)
2. daraus eine **begehbare Szene** bauen lassen (Panorama oder Gaussian Splatting)
3. **Marker setzen** (Klick ins Panorama bzw. in die 3D-Szene)
4. hinter jeden Marker **Inhalte hängen**: kurzer Film, Text, Bild, Audio, Links
5. die Szene **veröffentlichen** (statischer Export / Self-Hosting)

Anwendung: Waldszenen **und** Kulturerbe (Erinnerungs-Zwillinge von Wohnhäusern
mit Oral-History-Clips, Bon Pastor Barcelona).

---

## 2. Befund: Marker auf GitHub sind intakt

Marker je Szene in `docs/data/` am Stand `7886ba3`, verglichen mit dem Höchststand
über die gesamte Historie:

| Szene | jetzt | max. | Bemerkung |
|---|---|---|---|
| renon-setup01 | 87 | 87 | ok |
| consumer360-wilder-kaiser-wald | 10 | 10 | ok (am 27.09. wiederhergestellt, `3e80350`) |
| segforests-vienna-spruce / -beech | 121 / 66 | 121 / 66 | ok |
| hedgerow-be-alder | 19 | 19 | ok |
| syssifoss-arboretum / -br01 | 11 / 2 | 11 / 2 | ok |
| drjohnson-3dgs | 6 | 6 | ok (Story-Marker mit Bild/Text) |
| barberini-01…10 | 1–2 | 1–2 | ok (Portale) |
| renon-combined | 41 | 82 | **gewollt**: Fehldetektionen entfernt (`13c675d`, `8ad89fa`) |
| hvi-ahn-hedges | 173 | 214 | **gewollt**: Gebäude aus Punktwolke gefiltert (`6efb009`) |

**Folgerung:** Wenn auf dem Notebook Marker fehlen, liegt das an **lokalen, nicht
gepushten Änderungen** oder an Szenen, die nur im lokalen Studio-Speicher
(`platform/dev-data/`, Garage) liegen und nicht in Git.

### Prüfen auf dem Notebook (zuerst!)

```bash
git status
git fetch origin
git diff --stat origin/main
git log origin/main..HEAD --oneline      # lokale, nicht gepushte Commits
```

Wiederherstellen der Marker-Dateien vom GitHub-Stand (nur wenn lokal kaputt):

```bash
git checkout origin/main -- docs/data platform/web/gallery/scene.html platform/web/gallery/splat.html
```

### Bekannte Ursachen früherer Marker-Verluste (aus Commit `3e80350`)

1. **Seed-Skripte überschreiben `scene.json`** (z. B. `seed_commons_pano.py` ohne
   argparse → jeder Aufruf baut neu, `"markers": []`). Behoben für dieses Skript;
   **alle anderen Seed-/Build-Skripte auf dasselbe Muster prüfen** (vorhandene
   `markers/legend/stand/...` übernehmen statt verwerfen).
2. **Änderungen in `docs/` statt in der Quelle.** `docs/` ist **erzeugt** von
   `platform/dev/export_static.py`. Quelle ist `platform/web/gallery/`.

**Regeln für Claude Code:**
- `docs/` **nie von Hand** ändern. Immer `platform/web/gallery/*` ändern, dann exportieren.
- Kein Skript mit `--help` „ausprobieren“, das kein argparse hat.
- Vor/nach jedem Export Markerzahlen je Szene vergleichen (Skript siehe Abschn. 6).
- Keine großen Dateien committen (`.gitignore` beachten; große Splats → Hugging Face).

---

## 3. Was schon da ist

| Baustein | Ort | Stand |
|---|---|---|
| Studio-GUI: Upload → Job → Szene, Szenenliste, Löschen | `platform/web/studio/index.html` (324 Z.) | ✓ |
| Marker-Editor im Studio (Klick ins Panorama, yaw/pitch, Label) | dito, ab Z. 136 / 242 | ✓ nur Panorama, nur Label/Attribute |
| API | `platform/app/main.py`: `GET /api/scenes`, `GET /api/scenes/{sid}`, `POST /api/studio/upload`, `GET /api/studio/jobs[/{jid}]`, `PUT /api/studio/scenes/{sid}/markers`, `PATCH`/`DELETE /api/studio/scenes/{sid}` | ✓ |
| Verarbeitung: E57 → Reprojektion, Bilder → Hugin-Stitching | `platform/app/pipeline.py` | ✓ |
| Marker bleiben bei Neuverarbeitung erhalten | `pipeline.py` Z. ~233 | ✓ |
| Splat-Viewer mit **3D-verankerten Markern: Bild / Video / Text, Titel, Bildunterschrift, Credit** | `platform/web/gallery/splat.html` Z. ~214–261 | ✓ (Dr Johnson) |
| Panorama-Viewer mit Panels (`kind`), Infofenster, Auto-Rotation | `platform/web/gallery/scene.html` (1352 Z.) | ✓ |
| Portale zwischen Szenen (Rundgang) | Barberini-Szenen | ✓ |
| 3DGS-Training (COLMAP + gsplat), RunPod/Colab/Kaggle | `scripts/build_colmap.py`, `points_to_splat.py`, `clean_splat.py`, Notebooks | ✓ manuell, nicht im Studio |
| Statischer Export | `platform/dev/export_static.py` | ✓ |
| Docker / Self-Hosting (Caddy, Garage, FastAPI) | `platform/docker-compose.yml` | ✓ |
| Tests + CI | `tests/test_core.py`, `.github/workflows/tests.yml` | ✓ |

**Wichtig:** Der Splat-Viewer kann Video/Bild/Text hinter Markern schon anzeigen.
Es fehlt vor allem, dass **Nutzer das in der GUI selbst anlegen** können.

---

## 4. Was fehlt (Aufgabenliste, in dieser Reihenfolge)

### A. Einheitliches Marker-Schema (Basis für alles)
Ein Schema für Panorama **und** Splat:

```json
{
  "id": "m1",
  "anchor": { "type": "pano", "yaw": 12.3, "pitch": -4.1 },
  "_anchor_alt": { "type": "3d", "pos": [1.38, -0.14, 0.58] },
  "title": "Küche",
  "text": "Kurzer Text (Markdown, wird sicher gerendert)",
  "media": [
    { "type": "video", "src": "media/…/clip.mp4", "poster": "…jpg", "caption": "", "credit": "" },
    { "type": "image", "src": "…jpg", "caption": "", "credit": "" },
    { "type": "audio", "src": "…mp3" }
  ],
  "links": [ { "label": "Archiv MUHBA", "url": "https://…" } ],
  "time": { "from": 1952, "to": 1968, "phase": "Anbau Küche" },
  "provenance": "erinnert | dokumentiert | rekonstruiert | kuratiert",
  "rights": { "consent": "public | onsite | research | locked", "license": "CC BY 4.0" },
  "attributes": {},
  "demo": false
}
```

- **Abwärtskompatibel** lesen: alte Felder `yaw/pitch`, `pos`, `image`, `video`,
  `caption`, `credit`, `label`, `attributes` auf das neue Schema abbilden
  (Lesefunktion in beiden Viewern + Migrationsskript für `docs/data/*.json`).
- Bestehende Wald-Marker (Baumwerte in `attributes`, Panels über `kind`) dürfen
  sich **sichtbar nicht verändern**.

### B. API erweitern (`platform/app/main.py`)
- `PUT …/markers` verwirft derzeit alles außer `id/label/yaw/pitch/xyz/attributes/demo`
  → neues Schema annehmen (Whitelist), URLs prüfen, Text serverseitig bereinigen.
- **Neu:** `POST /api/studio/scenes/{sid}/media` — Upload Video/Bild/Audio in den
  Objektspeicher; Größenlimit; optional ffmpeg → MP4 (H.264) + Poster-Bild.

### C. Studio-Marker-Editor (`platform/web/studio/index.html`)
- Formular je Marker: Titel, Text, Medien hochladen/entfernen, Links, Zeit,
  Herkunft, Einwilligung; **Vorschau** wie im Viewer.
- **Splat-Szenen:** Marker per Klick in die 3D-Szene setzen (Raycast/Tiefe → `pos`).
  Dafür Editor-Modus in `splat.html` oder eingebetteter Viewer im Studio.
- Einfach halten: große Knöpfe, deutsche/spanische Beschriftung, keine Fachbegriffe.

### D. Viewer angleichen
- `scene.html` (Panorama) soll dieselben Medien-Marker zeigen wie `splat.html`
  (Video, Bild, Audio, Links). Gemeinsamen Render-Code in eine JS-Datei auslagern
  (`marker-card.js`), von beiden Viewern genutzt.

### E. Export
- `export_static.py`: nur Marker mit `rights.consent == "public"` exportieren;
  Medien mitkopieren; Markerzahl je Szene ausgeben.

### F. 3DGS im Studio (später, braucht GPU)
- Upload-Typ „Bildserie → 3D“: Job ruft COLMAP + gsplat lokal (CUDA) oder RunPod.

### G. Prüfen
- Tests für Schema-Migration, API-Whitelist, Consent-Filter.
- Nutzbarkeitstest mit Laien (Protokoll vorhanden:
  `Paper_ODT/Panorama_Pipeline_Paper/Nutzbarkeitstest_*`).

---

## 5. Erster Prompt für Claude Code (zum Kopieren)

> Lies `CLAUDE_CODE_UEBERGABE.md`, besonders Abschnitt 0. Prüfe zuerst mit git, ob lokal Marker gegenüber
> `origin/main` fehlen, und stelle sie ggf. wieder her (Abschnitt 2). Lege dann einen
> Branch `feature/medien-marker` an und setze Aufgabe A (einheitliches Marker-Schema,
> abwärtskompatibel) und D (gemeinsame `marker-card.js` für Panorama- und
> Splat-Viewer) um. Ändere nur Quellen unter `platform/`, exportiere danach mit
> `export_static.py` und vergleiche die Markerzahlen je Szene vor/nach. Zeig mir
> Dr Johnson und Wilder Kaiser im Browser, bevor du weitermachst.

---

## 6. Hilfsskript: Markerzahlen je Szene

```bash
python - <<'EOF'
import json, glob, os
for f in sorted(glob.glob('docs/data/scene-*.json')):
    n = len(json.load(open(f, encoding='utf-8')).get('markers') or [])
    print(f"{os.path.basename(f):45s} {n:4d}")
EOF
```

Sollwerte: siehe Tabelle in Abschnitt 2.
