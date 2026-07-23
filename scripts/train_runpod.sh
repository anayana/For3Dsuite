#!/usr/bin/env bash
# train_runpod.sh -- Renon 3D Gaussian Splatting auf einer gemieteten Linux-GPU
# (RunPod, vast.ai, Uni-Cluster). Kein Notebook, kein Google, kein Telefon.
#
# Zwei Pfade, automatisch nach CUDA-Version gewaehlt:
#   CUDA < 12.4  -> graphdeco 3DGS (baut die Submodule; klassisch, schnell)
#   CUDA >= 12.4 -> gsplat (wird gepflegt, baut auf neuem CUDA sauber). Das
#                   alte graphdeco-Repo kompiliert auf CUDA 12.8 NICHT -- daher
#                   dieser Weg, ohne dass ein anderes Template noetig ist.
# In beiden Faellen entsteht /workspace/renon_gaussians.ply (SuperSplat-Format).
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_runpod.sh | bash
set -euo pipefail

echo "=========================================================="
echo " Renon 3DGS -- Lauf auf $(hostname)"
echo "=========================================================="

command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU/nvidia-smi"; exit 1; }
nvidia-smi -L

# ---- Werkzeuge sicherstellen (viele RunPod-Images haben kein git/unzip) ----
# unzip ersetzen wir spaeter durch Python; git wird von beiden Pfaden gebraucht.
if ! command -v git >/dev/null; then
  echo "git fehlt -- installiere ..."
  (apt-get update -qq && apt-get install -y -qq git) \
    || { echo "FEHLER: git-Installation fehlgeschlagen (apt nicht verfuegbar?)"; exit 1; }
fi

python - <<'PY'
import torch
print("torch      :", torch.__version__)
print("CUDA(torch):", torch.version.cuda)
assert torch.cuda.is_available(), "torch sieht keine GPU"
cap = torch.cuda.get_device_capability(0)
print("GPU        :", torch.cuda.get_device_name(0), "-> CC", f"{cap[0]}.{cap[1]}")
open("/tmp/arch", "w").write(f"{cap[0]}.{cap[1]}")
# CUDA-Hauptversion fuer die Pfadwahl
maj, mnr = (torch.version.cuda or "0.0").split(".")[:2]
open("/tmp/cuda", "w").write(f"{maj}{mnr.zfill(2)}")   # z.B. 1208, 1181
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"
CUDA_NUM="$(cat /tmp/cuda)"

# ---- Datensatz finden oder aus dem Repo laden ----------------------------
REPO_ZIP="https://raw.githubusercontent.com/anayana/For3Dsuite/main/data/renon/colmap_renon4.zip"
ZIP="${1:-}"
[ -z "$ZIP" ] && ZIP="$(find /workspace . -maxdepth 3 -name colmap_renon4.zip 2>/dev/null | head -1)"
if [ -z "$ZIP" ] || [ ! -f "$ZIP" ]; then
  echo "Zip nicht lokal -- lade aus dem Repo ..."
  ZIP=/workspace/colmap_renon4.zip
  curl -fsSL "$REPO_ZIP" -o "$ZIP" || { echo "FEHLER: Download fehlgeschlagen"; exit 1; }
fi
rm -rf /workspace/renon && mkdir -p /workspace/renon
# Entpacken mit Python statt unzip -- unzip fehlt auf vielen RunPod-Images
python - "$ZIP" /workspace/renon <<'PY'
import sys, zipfile
zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])
print("entpackt:", sys.argv[1])
PY
DATA=/workspace/renon
[ -d "$DATA/sparse" ] || DATA="$(dirname "$(find /workspace/renon -maxdepth 2 -name sparse -type d | head -1)")"
N=$(ls "$DATA/images/"*.jpg 2>/dev/null | wc -l)
echo "Datensatz: $DATA | Bilder: $N"
[ "$N" -eq 20 ] || { echo "FEHLER: 20 Bilder erwartet, $N gefunden"; exit 1; }

OUTPLY=/workspace/renon_gaussians.ply

if [ "$CUDA_NUM" -lt 1240 ]; then
  # ================= Pfad A: graphdeco 3DGS (altes CUDA) ==================
  echo "== Pfad graphdeco (CUDA < 12.4) =="
  command -v nvcc >/dev/null || { echo "FEHLER: nvcc fehlt -- CUDA-*devel*-Template noetig"; exit 1; }
  cd /workspace
  [ -d gaussian-splatting ] || git clone --recursive --depth 1 https://github.com/graphdeco-inria/gaussian-splatting
  cd gaussian-splatting
  pip install -q ninja plyfile opencv-python joblib
  pip install -q --no-build-isolation ./submodules/diff-gaussian-rasterization \
      ./submodules/simple-knn ./submodules/fused-ssim
  echo "== Training (30k, -r 2) =="
  python train.py -s "$DATA" -m /workspace/output/renon --iterations 30000 -r 2
  cp /workspace/output/renon/point_cloud/iteration_30000/point_cloud.ply "$OUTPLY"
else
  # ================= Pfad B: gsplat (neues CUDA, kein Bauen) ==============
  echo "== Pfad gsplat (CUDA >= 12.4, baut die Submodule nicht) =="
  pip install -q plyfile
  pip install -q gsplat
  cd /workspace
  [ -d gsplat ] || git clone --depth 1 https://github.com/nerfstudio-project/gsplat
  pip install -q -r gsplat/examples/requirements.txt
  echo "== Training (30k Schritte) =="
  python gsplat/examples/simple_trainer.py default \
      --data_dir "$DATA" --data_factor 1 --max_steps 30000 \
      --result_dir /workspace/gsout --disable_viewer

  echo "== Exportiere PLY (gsplat-Checkpoint -> SuperSplat-Format) =="
  python - "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
out = sys.argv[1]
ck = sorted(glob.glob("/workspace/gsout/**/ckpts/*.pt", recursive=True)
            + glob.glob("/workspace/gsout/ckpts/*.pt"))
assert ck, "kein gsplat-Checkpoint gefunden"
s = torch.load(ck[-1], map_location="cpu")
s = s["splats"] if "splats" in s else s
g = lambda k: s[k].detach().cpu().numpy()
means = g("means").astype(np.float32)
N = means.shape[0]
scales = g("scales").astype(np.float32)          # roh (log) -- wie INRIA
quats  = g("quats").astype(np.float32)           # roh (wxyz) -- wie INRIA
opac   = g("opacities").astype(np.float32).reshape(N, 1)   # roh (logit)
fdc    = g("sh0").astype(np.float32).reshape(N, 3)
shN    = g("shN").astype(np.float32)             # (N,K,3)
frest  = shN.transpose(0, 2, 1).reshape(N, -1)   # kanal-major, wie INRIA
cols = ["x","y","z","nx","ny","nz"] + ["f_dc_0","f_dc_1","f_dc_2"] \
     + [f"f_rest_{i}" for i in range(frest.shape[1])] + ["opacity"] \
     + ["scale_0","scale_1","scale_2"] + ["rot_0","rot_1","rot_2","rot_3"]
data = np.concatenate([means, np.zeros((N,3),np.float32), fdc, frest,
                       opac, scales, quats], axis=1).astype(np.float32)
el = np.empty(N, dtype=[(c, "f4") for c in cols])
for i, c in enumerate(cols):
    el[c] = data[:, i]
PlyData([PlyElement.describe(el, "vertex")]).write(out)
print(f"-> {out}  ({N:,} Gaussians)")
PY
fi

[ -f "$OUTPLY" ] || { echo "FEHLER: kein Ergebnis-PLY -- Log oben pruefen"; exit 1; }
echo "=========================================================="
echo " FERTIG -> $OUTPLY  ($(du -h "$OUTPLY" | cut -f1))"
echo " Per JupyterLab herunterladen, dann Drag&Drop in"
echo " https://playcanvas.com/supersplat/editor"
echo "=========================================================="
