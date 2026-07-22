# Renon — 3D Gaussian Splatting Trainings-Datensatz

Aufbereitet aus den E57-Pinhole-Bildern + LiDAR (kein COLMAP-SfM nötig, weil die
Kameraposen exakt aus den E57-`pinholeRepresentation`-Blöcken stammen und die
LiDAR-Wolke die Initialisierung liefert). Erzeugt mit `scripts/build_colmap.py`.

## Struktur (COLMAP-Format)

```
data/renon/colmap/
├── images/               Pinhole-JPEGs, Name sNNN_cMM.jpg (Setup NNN, Kamera MM)
└── sparse/0/
    ├── cameras.txt       1 Kamera, Modell PINHOLE 2048x2048, f≈1023.5 px (=90° HFOV)
    ├── images.txt        Extrinsics world→camera (OpenCV-Konvention), pro Bild
    └── points3D.txt      LiDAR-Initialwolke mit RGB (gemeinsamer E57-Weltframe)
```

Alle Bilder teilen dieselben Intrinsics. Die Nadir-Kamera (c06, vom Stativ maskiert)
ist standardmäßig weggelassen. Posen und Punkte liegen im **selben** (registrierten)
E57-Weltkoordinatensystem, in dem auch die Standpunkte ~3 m auseinander liegen.

## Warum das gut funktionieren sollte

- **Posen exakt** → kein SfM-Schätzfehler, kein „COLMAP schlägt fehl im Wald".
- **LiDAR-Init** → Gaussians starten auf echter Geometrie statt aus zufälligem SfM-Sparse;
  spart Iterationen und stabilisiert dünne Strukturen (Stämme, Äste).
- Wenige Bilder (≈ 5 je Standpunkt) — mehr Standpunkte verbessern die Neuansichts-Qualität
  deutlich. Für einen ersten Lauf reichen 4 Standpunkte (~20 Bilder).

## Training auf einer Cloud-GPU

Lokal (Quadro M2000M, 4 GB) reicht nicht — 8–16 GB VRAM nötig. Optionen: Google Colab
(kostenlose T4, 16 GB), oder gemietete GPU (RunPod/vast.ai).

### A) Original 3DGS (graphdeco-inria)

```bash
git clone https://github.com/graphdeco-inria/gaussian-splatting --recursive
cd gaussian-splatting
pip install plyfile opencv-python joblib
# DREI Submodule -- fused-ssim ist seit Ende 2024 Pflicht, fehlt es, bricht
# train.py sofort mit ModuleNotFoundError ab:
pip install --no-build-isolation ./submodules/diff-gaussian-rasterization \
    ./submodules/simple-knn ./submodules/fused-ssim

# Datensatz-Ordner (images/ + sparse/0/) hierher kopieren, z.B. nach data/renon
python train.py -s /pfad/zu/data/renon/colmap -m output/renon \
    --iterations 30000 -r 2        # -r 2 = auf 1024 px runterskalieren (VRAM-schonend)

# Ergebnis: output/renon/point_cloud/iteration_30000/point_cloud.ply  (die Gaussians)
```

Bei knappem VRAM: `-r 2` (oder `-r 4`), ggf. `--densify_until_iter 15000`.

### B) gsplat / nerfstudio (alternativ, moderner)

```bash
pip install nerfstudio
ns-train splatfacto --data /pfad/zu/data/renon/colmap colmap
# oder gsplat direkt: examples/simple_trainer.py mit COLMAP-Parser
```

### Colab

[`train_colab.ipynb`](train_colab.ipynb) in Colab öffnen, Laufzeit auf GPU (T4)
stellen, Zellen der Reihe nach. In Zelle 3 `colmap_renon4.zip` (15 MB, liegt in
`data/Renon/`) hochladen. Das Notebook prüft vorab torch/CUDA, setzt
`TORCH_CUDA_ARCH_LIST` passend zur zugeteilten GPU und importiert die drei
Submodule hart, statt dem stillen `pip -q` zu vertrauen. Scheitert der
CUDA-Build trotzdem (passiert, sobald Colab eine neuere torch-Version ausrollt),
ersetzt die letzte Code-Zelle Bau **und** Training durch nerfstudio/`gsplat`
mit vorkompilierten Wheels.

## Ergebnis ansehen

Die trainierten Gaussians (`point_cloud.ply`, 3DGS-Format) laufen in:
- **SuperSplat** (playcanvas, Browser) — Drag&Drop, sofort begehbar.
- **antimatter15/splat** oder **gsplat.js** — three.js-basiert, in unseren Viewer integrierbar.
- Damit ist der **fließende, fotorealistische Spaziergang** möglich — freie Kamera,
  korrekte Parallaxe, Laub inklusive.

## Reproduktion des Datensatzes

```bash
python scripts/build_colmap.py "data/renon/e57/*.e57" data/renon/colmap \
    --init-points 300000 --per-setup-points 100000
```

Mehr Standpunkte: weitere Setups mit `scripts/zip_remote.py getnested … <N>` ziehen,
dann `build_colmap.py` erneut über alle `*.e57` laufen lassen.
