#!/usr/bin/env bash
# train_drjohnson_runpod.sh -- 3D Gaussian Splatting von "Dr Johnson's House"
# (Deep-Blending-Datensatz, bereits COLMAP-aufbereitet) auf einer gemieteten
# Linux-GPU (RunPod). Du musst NUR diesen einen Befehl auf dem Pod ausfuehren:
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_drjohnson_runpod.sh | bash
#
# Das Skript laedt den Datensatz, trainiert das 3DGS, verkleinert es auf ein
# viewer-fertiges .ply und laedt es zu einem Einweg-Link hoch. Am Ende steht eine
# URL -- die schickst du mir zurueck, den Rest (Szene, Erzaehlung, Marker,
# Veroeffentlichen) mache ich.
#
# Empfohlener Pod: eine CUDA-*devel*-Vorlage (z. B. "RunPod PyTorch 2.x, CUDA
# 11.8 devel" oder "12.1 devel") mit >=16 GB VRAM (RTX A4000/A4500/3090/4090).
# Der devel-Teil ist wichtig -- ohne nvcc kann der graphdeco-Pfad nicht bauen.
set -euo pipefail

echo "=========================================================="
echo " Dr Johnson's House 3DGS -- Lauf auf $(hostname)"
echo "=========================================================="
command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU/nvidia-smi"; exit 1; }
nvidia-smi -L

# ---- Werkzeuge ----
if ! command -v git >/dev/null; then
  echo "git fehlt -- installiere ..."
  apt-get update -qq && apt-get install -y -qq git \
    || { echo "FEHLER: git-Installation fehlgeschlagen"; exit 1; }
fi
command -v curl >/dev/null || { apt-get update -qq && apt-get install -y -qq curl; }

python - <<'PY'
import torch
print("torch      :", torch.__version__)
print("CUDA(torch):", torch.version.cuda)
assert torch.cuda.is_available(), "torch sieht keine GPU"
cap = torch.cuda.get_device_capability(0)
print("GPU        :", torch.cuda.get_device_name(0), "-> CC", f"{cap[0]}.{cap[1]}")
open("/tmp/arch", "w").write(f"{cap[0]}.{cap[1]}")
maj, mnr = (torch.version.cuda or "0.0").split(".")[:2]
open("/tmp/cuda", "w").write(str(int(maj) * 100 + int(mnr)))
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"
CUDA_NUM="$(cat /tmp/cuda)"

# ---- Datensatz: Deep Blending (Tanks&Temples + DB), enthaelt db/drjohnson ----
cd /workspace 2>/dev/null || cd /root
if [ ! -d db/drjohnson/sparse ]; then
  echo "== Lade Deep-Blending-Datensatz (~660 MB) =="
  curl -fL "https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip" \
       -o tandt_db.zip || { echo "FEHLER: Datensatz-Download fehlgeschlagen"; exit 1; }
  python - <<'PY'
import zipfile
z = zipfile.ZipFile("tandt_db.zip")
z.extractall(".")     # legt tandt/ und db/ an
print("entpackt")
PY
fi
DATA="$(pwd)/db/drjohnson"
[ -d "$DATA/sparse" ] || DATA="$(dirname "$(find . -maxdepth 3 -path '*drjohnson/sparse' -type d | head -1)")"
NIMG=$(ls "$DATA/images/" 2>/dev/null | wc -l)
echo "Datensatz: $DATA | Bilder: $NIMG"
[ "$NIMG" -gt 50 ] || { echo "FEHLER: zu wenige Bilder in $DATA"; exit 1; }

OUTPLY=/workspace/drjohnson_gaussians.ply
[ -d /workspace ] || OUTPLY=/root/drjohnson_gaussians.ply

# ===== gsplat -- baut kein diff_gaussian_rasterization, laeuft auf jeder CUDA =====
echo "== Pfad gsplat (kein C++-Build noetig, CUDA_NUM=$CUDA_NUM) =="
[ -d gsplat ] || git clone --recursive --depth 1 https://github.com/nerfstudio-project/gsplat
# Untermodule (u.a. glm) sicher nachladen -- sonst: "fatal error: glm/gtc/type_ptr.hpp"
git -C gsplat submodule update --init --recursive
pip install -q ninja plyfile
# WICHTIG: nvcc-Builds sonst OOM-gekillt ("Error compiling objects for extension")
# -- Parallelitaet begrenzen. Nur fuer die aktuelle GPU-Architektur bauen (spart
# Zeit und Speicher).
export MAX_JOBS="${MAX_JOBS:-4}"
echo "== Baue mit MAX_JOBS=$MAX_JOBS, TORCH_CUDA_ARCH_LIST=$TORCH_CUDA_ARCH_LIST =="
# torch ist im Pod schon da -- --no-build-isolation, damit die C++/CUDA-Pakete es
# beim Bauen sehen (sonst: "No module named 'torch'"). Beispiel-Abhaengigkeiten
# zuerst (setzen torch endgueltig, bauen fused-ssim dagegen).
pip install -q pillow
pip install --no-build-isolation -r gsplat/examples/requirements.txt
# gsplat-Bibliothek AUS DEM GECLONTEN Quellcode bauen, damit sie exakt zu den
# Beispielen passt (sonst fehlt z.B. gsplat.color_correct). Ohne -q, damit ein
# echter Compilerfehler sichtbar bleibt. Bei einem Neulauf ueberspringen, wenn die
# passende Quellversion schon installiert ist (spart den Rebuild).
python -c "import gsplat.color_correct" 2>/dev/null \
  && echo "gsplat (Quellversion) schon installiert -- Build uebersprungen" \
  || pip install --no-build-isolation ./gsplat

# data_factor 2 erwartet halbaufgeloeste Bilder in images_2/ -- der Deep-Blending-
# Satz liefert nur images/. Einmalig erzeugen (sonst: "Image folder images_2 does not exist").
FACTOR=2
if [ ! -d "$DATA/images_$FACTOR" ]; then
  echo "== Erzeuge halbaufgeloeste Bilder images_$FACTOR (fuer data_factor=$FACTOR) =="
  python - "$DATA" "$FACTOR" <<'PY'
import os, sys
from PIL import Image
data, factor = sys.argv[1], int(sys.argv[2])
src = os.path.join(data, "images"); dst = os.path.join(data, f"images_{factor}")
os.makedirs(dst, exist_ok=True)
n = 0
for f in sorted(os.listdir(src)):
    try:
        im = Image.open(os.path.join(src, f)).convert("RGB")
    except Exception:
        continue
    im.resize((im.width // factor, im.height // factor), Image.LANCZOS).save(os.path.join(dst, f))
    n += 1
print(f"erzeugt: {dst} ({n} Bilder)")
PY
fi

echo "== Training (30k) -- dauert je nach GPU ~30-45 min =="
python gsplat/examples/simple_trainer.py default \
    --data_dir "$DATA" --data_factor "$FACTOR" --max_steps 30000 \
    --result_dir /workspace/gsout --disable_viewer
echo "== Exportiere PLY (gsplat -> INRIA/SuperSplat-Format) =="
python - "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
out = sys.argv[1]
ck = sorted(glob.glob("/workspace/gsout/**/ckpts/*.pt", recursive=True))
assert ck, "kein gsplat-Checkpoint gefunden"
s = torch.load(ck[-1], map_location="cpu"); s = s.get("splats", s)
g = lambda k: s[k].detach().cpu().numpy()
means = g("means").astype(np.float32); N = means.shape[0]
scales = g("scales").astype(np.float32); quats = g("quats").astype(np.float32)
opac = g("opacities").astype(np.float32).reshape(N, 1)
fdc = g("sh0").astype(np.float32).reshape(N, 3)
frest = g("shN").astype(np.float32).transpose(0, 2, 1).reshape(N, -1)
cols = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2"] \
     + [f"f_rest_{i}" for i in range(frest.shape[1])] + ["opacity"] \
     + ["scale_0","scale_1","scale_2"] + ["rot_0","rot_1","rot_2","rot_3"]
data = np.concatenate([means, np.zeros((N,3),np.float32), fdc, frest, opac, scales, quats], 1).astype(np.float32)
el = np.empty(N, dtype=[(c,"f4") for c in cols])
for i,c in enumerate(cols): el[c] = data[:, i]
PlyData([PlyElement.describe(el,"vertex")]).write(out)
print(f"-> {out} ({N:,} Gaussians)")
PY

[ -f "$OUTPLY" ] || { echo "FEHLER: kein Ergebnis-PLY -- Log oben pruefen"; exit 1; }
echo "== Verkleinere auf viewer-fertiges .ply (SH-Grad 0, ~700k) =="
pip install -q plyfile numpy
curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/ply_reduce.py -o /tmp/ply_reduce.py
REDPLY="$(dirname "$OUTPLY")/drjohnson_reduced.ply"
python /tmp/ply_reduce.py "$OUTPLY" "$REDPLY" --keep 700000

echo "== Lade das Ergebnis zu einem Einweg-Link hoch =="
URL="$(curl -fsSL -F"file=@$REDPLY" https://0x0.st 2>/dev/null || true)"
echo "=========================================================="
echo " FERTIG."
echo "   voll:      $OUTPLY  ($(du -h "$OUTPLY" | cut -f1))"
echo "   reduziert: $REDPLY  ($(du -h "$REDPLY" | cut -f1))"
if [ -n "$URL" ]; then
  echo ""
  echo " >>> SCHICK MIR DIESE URL ZURUECK: $URL"
else
  echo ""
  echo " Auto-Upload fehlgeschlagen -- lade $REDPLY per JupyterLab-Dateibrowser"
  echo " herunter und schick mir die Datei."
fi
echo "=========================================================="
