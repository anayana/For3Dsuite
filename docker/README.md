# For3Dsuite in Docker — reproduzierbar

Zwei getrennte Images, weil sich die Anforderungen unterscheiden: die **CPU-Pipeline**
(Inventur, RGB-Analyse, Wuchsmodell-Export, begehbarer Viewer) läuft überall; das
**3DGS-Training** braucht eine **GPU/CUDA**.

## 1. CPU: Suite + reproduzierbarer Lauf (kein GPU)

```bash
docker compose -f docker/compose.yml up --build
# -> http://localhost:8000/   Startseite, Karte, Szenen, begehbarer Splat-Viewer
```

Beim Start führt der Container eine **Offline-Reproduktion** aus (Log): Wuchsprognose
aus den committeten Renon-Daten (`data/renon/trees_setup001.csv`) — ohne GPU, ohne Netz,
ohne die GPL-JAR. Danach serviert er die statische Suite aus `docs/`.

Einzelne Pipeline-Schritte im selben Image:
```bash
docker build -f docker/Dockerfile -t for3d .
docker run --rm -v "$PWD:/app" for3d python scripts/inventory_from_cloud.py scan.e57 trees.csv
docker run --rm for3d reproduce         # nur die Reproduktion, ohne Server
```

**Optionale schwere Leser** sind nicht im Basis-Image (schlank gehalten): E57 (`pye57`)
und GeoTIFF-Sampling (`rasterio`, `pyproj`). Bei Bedarf ins `docker/requirements.txt`
aufnehmen und neu bauen.

## 2. GPU: 3D Gaussian Splatting — zwei Wege, gleiche Logik

Das Training kompiliert CUDA-Kernel → **CUDA-*devel* mit `nvcc` ist Pflicht**.

**a) Lokaler/HPC-CUDA-Container**
```bash
docker build -f docker/Dockerfile.gpu -t for3d-gpu .
docker run --gpus all -v "$PWD/out:/workspace" for3d-gpu \
    bash scripts/train_mipnerf.sh stump
# -> /workspace/stump_gaussians.ply
```
Auf HPC ohne Docker-Daemon lässt sich das Image mit **Apptainer/Singularity** ziehen
(`apptainer build for3d-gpu.sif docker://…`).

**b) Gemietete GPU (RunPod/vast.ai) ohne eigenen Container**
```bash
curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_mipnerf.sh | bash -s stump
```
(Pod-Template mit **`-devel`/CUDA ≥ 12.4** wählen.)

**Ergebnis weiterverarbeiten** (CPU): Hintergrund/Floater entfernen und als begehbare
Szene einhängen —
```bash
python scripts/clean_splat.py stump_gaussians.ply stump_clean.ply --sh0 --max 500000
python platform/dev/seed_splat.py stump_clean.ply --id my-splat --title "…"
```
Große `.ply` extern (Hugging Face, CORS-fähig) hosten und per `--external-url` einhängen;
GitHub-Release-Assets senden **kein** CORS und funktionieren im Viewer nicht.

## Lizenz-Hinweis
Die echte Wuchs-Engine **TreeGrOSS ist GPLv3** und liegt NICHT im Image (nur der
Python-Demonstrator). Für die echte Engine `growth-service/` bauen (Maven + JAR von der
NW-FVA, siehe growth-service/README) — die GPL-Komponente bleibt als eigener Dienst
isoliert.

## Status
CPU-Image und Reproduktionsschritt sind auf einer normalen Maschine lauffähig. Das
GPU-Image spiegelt die auf RunPod erprobte Trainingslogik; Bauen/Verifizieren erfordert
eine CUDA-*devel*-Maschine.
