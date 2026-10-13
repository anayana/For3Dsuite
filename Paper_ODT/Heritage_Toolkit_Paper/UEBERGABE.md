# Übergabe: Heritage-/Museums-Paper (Paper B)

Stand 13.10.2026 · Repo `anayana/For3Dsuite` · Autor: Angel Naya, Independent Researcher, Berlin
(angel.naya@posteo.de) · Konzept: `Heritage_Toolkit_Konzept.md` (dieser Ordner)

## 0. Arbeitsweise mit dem Nutzer (verbindlich)

- Deutsch, **kurz und konkret**. Kein Füllstoff, keine langen Optionslisten. Nur exakte
  Bezeichnungen/Links; nichts raten — wenn etwas nicht prüfbar ist, das in einem Satz sagen.
- Nutzer arbeitet **vom Handy**, ohne lokales Docker. PRs mergt **der Nutzer** (Agent darf nicht mergen).
- **Kein Geld:** nur Journals ohne Pflicht-Publikationsgebühr. **GPU: RunPod erlaubt** (Nutzer-
  Entscheidung 13.10.2026; gemietet, ca. 0,20 € je Lauf laut `README_TRAINING.md`; vorhandenes
  Muster `scripts/train_runpod.sh`). **Kein Google** (auch nicht Colab, Kaggle) — Nutzer-
  Entscheidung 13.10.2026. Sonstige kostenpflichtige Dienste (HF-Spaces o. ä.) weiterhin nicht.
- **Nur offene Fremddaten und FOSS**, keine eigenen Aufnahmen/Interviews (derzeit). Lizenzen prüfen
  (`DATA_SOURCES.md`).
- **Petra (CULTURE3D), Dr Johnson (Deep Blending), Stump (Mip-NeRF 360): keine Datenlizenz gefunden**
  → im Paper höchstens als zitierter Benchmark, nicht öffentlich weitergeben (sind aus der Galerie
  zurückgehalten, `platform/dev/publish.json`).
- **Nicht `platform/dev/export_static.py` ohne `--html-only` ausführen** (siehe
  `CLAUDE_CODE_UEBERGABE.md`, Abschn. 0).
- Aus der Cloud-Umgebung gesperrt: zenodo.org, sciencedirect.com, arxiv.org, huggingface.co,
  crossref. Bei Bedarf den Nutzer um Inhalte bitten.

## 1. Ziel des Papers (technisch, mit offenen Daten machbar)

Arbeitstitel: **3D Gaussian Splatting gegen photogrammetrische Referenz an historischen Gebäuden —
plus offenes Werkzeug, um daraus erzählte Rundgänge mit Medien-Markern zu bauen.**

- Messteil (vermessungstechnisch, Zielgruppe Denkmalpflege/3D-Vermessung): 3DGS aus offenen
  Bildserien trainieren und geometrisch gegen die Referenz-Punktwolke prüfen.
- Werkzeugteil: einheitliches Marker-Schema, `marker-card.js`, Browser-Studio `create.html`
  (offline lauffähige Szene als eine HTML-Datei, kein Server).
- Oral-History-Teil des Konzepts (Interviews, Laientest) **nicht** in diesem Paper — braucht eigene
  Erhebung.

## 2. Kandidat-Datensatz (Lizenz vom Nutzer bestätigen lassen!)

**Pellis, Masiero, Betti, Tucci, Grussenmeyer (2025), Data in Brief 60, doi 10.1016/j.dib.2025.111661**,
Daten Zenodo 14626611 („Images&PointClouds Cultural Heritage Dataset"): 5 historische Gebäude,
Fotos **mit Kameraparametern (intrinsisch/extrinsisch)**, georeferenzierte Punktwolken mit
Bauteil-Labels. Laut Suchergebnis CC BY 4.0 — Zenodo ist von hier gesperrt, Lizenz vom Nutzer
auf der Zenodo-Seite ablesen lassen.
Alternativen (CC BY 4.0 laut Suche): Massa Marittima (Zenodo 16575516), Paganico (16576623),
Rigomagno (16575949); Dalibor-Turm Prag (Zenodo 1458271, CC BY-SA 4.0).

## 3. Was im Repo schon da ist

| Baustein | Datei |
|---|---|
| Marker-Schema (alt+neu), Lesefunktion, Migration, Tests | `platform/web/gallery/marker-card.js`, `platform/app/marker_schema.py`, `platform/dev/migrate_markers.py`, `tests/test_marker_schema.py` |
| Medien-Karte für Panorama + Splat | `marker-card.js`, `scene.html`, `splat.html` |
| Browser-Studio (online: https://anayana.github.io/For3Dsuite/create.html) | `platform/web/gallery/create.html` |
| 3DGS-Training (gsplat), COLMAP, Aufräumen, Viewer | `scripts/build_colmap.py`, `train_*.sh`, `clean_splat.py`, `ply_reduce.py`, `splat.html`; RunPod: `scripts/train_runpod.sh` |
| Portale/Rundgang (Barberini, CC BY-SA) | `platform/dev/seed_barberini.py` |

## 4. Offene Aufgaben (Reihenfolge)

1. Lizenz und Dateiformat des Pellis-Datensatzes klären (Nutzer schaut auf Zenodo nach).
2. Trainings-Rezept für **RunPod** mit vorhandenen Kameraposen (COLMAP-Schritt
   entfällt oder nur Format-Umwandlung).
3. Geometrie-Prüfung: Splat-Zentren bzw. gerenderte Tiefe gegen Referenzwolke (C2C-Abstände,
   Vollständigkeit), je Gebäude und Bauteilklasse.
4. Eine Szene als erzählter Rundgang mit Medien-Markern (Browser-Studio) als Demonstration.
5. Manuskript.

## 5. Journals (Pflicht: ohne Gebühr) — vor Einreichung APC-Regel prüfen

Kandidaten: *Journal of Cultural Heritage* (Elsevier, Hybrid, Abo-Weg), *Digital Applications in
Archaeology and Cultural Heritage* (Elsevier), *PFG* (Springer, Hybrid). Prüfen: *Virtual
Archaeology Review* (Angaben zur APC widersprüchlich: 0 vs. 499 €). **Nicht:** *Heritage Science*
(Gold-OA mit APC), MDPI *Heritage*.

## 6. Bezug

- Paper A (Software, Computers & Geosciences): `Paper_ODT/Panorama_Pipeline_Paper/`.
- Konzept mit Erinnerungsebene, Ethik, Datenmodell: `Heritage_Toolkit_Konzept.md`.

## 7. Erster Schritt für die neue Sitzung

`Heritage_Toolkit_Konzept.md` und diese Datei lesen → den Nutzer die Lizenz des
Pellis-Datensatzes auf Zenodo ablesen lassen (Link: https://zenodo.org/records/14626611) →
danach Plan als `Paper_ODT/Heritage_Toolkit_Paper/PLAN.md` vorlegen.
