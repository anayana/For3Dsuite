#!/usr/bin/env bash
# train_runpod.sh -- Renon 3D Gaussian Splatting auf einer gemieteten Linux-GPU
# (RunPod, vast.ai, Uni-Cluster -- ueberall gleich). Kein Notebook, kein Google,
# kein Telefon. Der Datensatz wird bei Bedarf selbst aus dem Repo geladen.
#
# RunPod in drei Schritten:
#   1. Pod mit Template "RunPod PyTorch 2.x" (CUDA-devel, hat nvcc) mieten,
#      GPU mit >=12 GB (RTX 3090/4090, A4000, L4 ...). ~0,20-0,40 $/h.
#   2. Im Web-Terminal EIN Befehl:
#        curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_runpod.sh | bash
#   3. Nach ~30 Min: /workspace/renon_gaussians.ply per JupyterLab laden,
#      Drag&Drop in https://playcanvas.com/supersplat/editor
#
# Manuell mit eigener Zip:  bash train_runpod.sh pfad/zu/colmap_renon4.zip
set -euo pipefail

echo "=========================================================="
echo " Renon 3DGS -- Lauf auf $(hostname)"
echo "=========================================================="

# ---- 1) Umgebung pruefen -------------------------------------------------
command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU/nvidia-smi"; exit 1; }
nvidia-smi -L
command -v nvcc >/dev/null || { echo "FEHLER: nvcc fehlt -- ein CUDA-*devel*-Template"
  echo "        waehlen (RunPod PyTorch hat es), sonst bauen die Submodule nicht."; exit 1; }

python - <<'PY'
import torch, sys
print("torch      :", torch.__version__)
print("CUDA(torch):", torch.version.cuda)
assert torch.cuda.is_available(), "torch sieht keine GPU"
cap = torch.cuda.get_device_capability(0)
print("GPU        :", torch.cuda.get_device_name(0), "-> CC", f"{cap[0]}.{cap[1]}")
open("/tmp/arch", "w").write(f"{cap[0]}.{cap[1]}")
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"
echo "Baue fuer Compute Capability $TORCH_CUDA_ARCH_LIST"

# ---- 2) Datensatz finden (oder aus dem Repo laden) -----------------------
REPO_ZIP="https://raw.githubusercontent.com/anayana/For3Dsuite/main/data/renon/colmap_renon4.zip"
ZIP="${1:-}"
if [ -z "$ZIP" ]; then
  ZIP="$(find /workspace . -maxdepth 3 -name colmap_renon4.zip 2>/dev/null | head -1)"
fi
if [ -z "$ZIP" ] || [ ! -f "$ZIP" ]; then
  echo "Zip nicht lokal -- lade aus dem Repo ..."
  ZIP=/workspace/colmap_renon4.zip
  curl -fsSL "$REPO_ZIP" -o "$ZIP" || { echo "FEHLER: Download fehlgeschlagen."
    echo "        Zip manuell nach /workspace hochladen (JupyterLab)."; exit 1; }
fi
echo "Datensatz: $ZIP"
rm -rf /workspace/renon && mkdir -p /workspace/renon
unzip -q -o "$ZIP" -d /workspace/renon
DATA=/workspace/renon
[ -d "$DATA/sparse" ] || DATA="$(dirname "$(find /workspace/renon -maxdepth 2 -name sparse -type d | head -1)")"
N=$(ls "$DATA/images/"*.jpg 2>/dev/null | wc -l)
echo "  Wurzel: $DATA  | Bilder: $N"
[ "$N" -eq 20 ] || { echo "FEHLER: 20 Bilder erwartet, $N gefunden"; exit 1; }

# ---- 3) 3DGS bauen -------------------------------------------------------
cd /workspace
if [ ! -d gaussian-splatting ]; then
  git clone --recursive --depth 1 https://github.com/graphdeco-inria/gaussian-splatting
fi
cd gaussian-splatting
pip install -q ninja plyfile opencv-python joblib
# DREI Submodule -- fused-ssim ist seit Ende 2024 Pflicht, sonst bricht train.py ab.
pip install -q --no-build-isolation \
  ./submodules/diff-gaussian-rasterization \
  ./submodules/simple-knn \
  ./submodules/fused-ssim
python - <<'PY'
import importlib
for m in ("diff_gaussian_rasterization", "simple_knn._C", "fused_ssim"):
    importlib.import_module(m); print("OK:", m)
PY

# ---- 4) Training ---------------------------------------------------------
echo "== Training (30k Iterationen, -r 2) =="
python train.py -s "$DATA" -m /workspace/output/renon --iterations 30000 -r 2

# ---- 5) Ergebnis ablegen -------------------------------------------------
PLY=/workspace/output/renon/point_cloud/iteration_30000/point_cloud.ply
[ -f "$PLY" ] || { echo "FEHLER: kein Ergebnis-PLY -- Log oben pruefen"; exit 1; }
cp "$PLY" /workspace/renon_gaussians.ply
echo "=========================================================="
echo " FERTIG -> /workspace/renon_gaussians.ply ($(du -h "$PLY" | cut -f1))"
echo " Per JupyterLab-Dateibrowser herunterladen, dann Drag&Drop in"
echo " https://playcanvas.com/supersplat/editor"
echo "=========================================================="
