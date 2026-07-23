#!/usr/bin/env bash
# train_mipnerf.sh -- 3D Gaussian Splatting auf einer ECHTEN Mehransichts-Szene
# (Mip-NeRF 360, das 3DGS-Standard-Benchmark). Im Gegensatz zu den Renon-Panoramen
# haben diese Szenen 100-300 Fotos aus verschiedenen Positionen -> echte Parallaxe,
# fotorealistisches, begehbares Ergebnis statt Floater-Explosion.
#
# Vegetationsszenen: stump (Waldboden+Stumpf), bicycle (Wiese/Baeume), garden,
#                    treehill, flowers.
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_mipnerf.sh | bash -s stump
#   (ohne Argument: stump)
set -euo pipefail

SCENE="${1:-stump}"
echo "=========================================================="
echo " Mip-NeRF 360 3DGS -- Szene '$SCENE' auf $(hostname)"
echo "=========================================================="

command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU"; exit 1; }
nvidia-smi -L
command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }

python - <<'PY'
import torch
assert torch.cuda.is_available(), "torch sieht keine GPU"
maj, mnr = (torch.version.cuda or "0.0").split(".")[:2]
open("/tmp/cuda", "w").write(f"{maj}{mnr.zfill(2)}")
open("/tmp/arch", "w").write("{}.{}".format(*torch.cuda.get_device_capability(0)))
print("torch", torch.__version__, "CUDA", torch.version.cuda)
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"
CUDA_NUM="$(cat /tmp/cuda)"

# ---- Szene beschaffen (nur die eine aus dem Sammel-Zip extrahieren) ----------
cd /workspace
V2="bicycle bonsai counter garden kitchen room stump"
if echo "$V2" | grep -qw "$SCENE"; then ZIP=360_v2.zip; else ZIP=360_extra_scenes.zip; fi
if [ ! -d "/workspace/$SCENE/sparse" ]; then
  echo "== Lade $SCENE aus $ZIP =="
  curl -fL "https://storage.googleapis.com/gresearch/refraw360/$ZIP" -o "/workspace/$ZIP"
  python - "$ZIP" "$SCENE" <<'PY'
import sys, zipfile
zf = zipfile.ZipFile(sys.argv[1]); scene = sys.argv[2]
members = [n for n in zf.namelist() if n.split("/")[0] == scene]
assert members, f"Szene {scene} nicht im Zip -- verfuegbar: " \
    + ",".join(sorted({n.split('/')[0] for n in zf.namelist()}))
zf.extractall("/workspace", members)
print(f"{len(members)} Dateien fuer {scene} entpackt")
PY
  rm -f "/workspace/$ZIP"
fi
DATA="/workspace/$SCENE"
N=$(ls "$DATA/images/" 2>/dev/null | wc -l)
echo "Datensatz: $DATA | $N Bilder"
[ "$N" -ge 30 ] || { echo "FEHLER: zu wenige Bilder ($N)"; exit 1; }

OUTPLY="/workspace/${SCENE}_gaussians.ply"

if [ "$CUDA_NUM" -lt 1240 ]; then
  echo "== graphdeco (CUDA < 12.4) =="
  command -v nvcc >/dev/null || { echo "FEHLER: nvcc fehlt -- devel-Template noetig"; exit 1; }
  [ -d gaussian-splatting ] || git clone --recursive --depth 1 https://github.com/graphdeco-inria/gaussian-splatting
  cd gaussian-splatting
  pip install -q ninja plyfile opencv-python joblib tqdm
  pip install -q --no-build-isolation ./submodules/diff-gaussian-rasterization \
      ./submodules/simple-knn ./submodules/fused-ssim
  pip install -q "numpy<2"                       # torch 2.1 braucht numpy<2
  echo "== Training (30k, -r 4 = auf ~1/4 Aufloesung, VRAM-schonend) =="
  python train.py -s "$DATA" -m /workspace/output/"$SCENE" --iterations 30000 -r 4
  cp /workspace/output/"$SCENE"/point_cloud/iteration_30000/point_cloud.ply "$OUTPLY"
else
  echo "== gsplat (CUDA >= 12.4) =="
  pip install -q plyfile gsplat
  [ -d gsplat ] || git clone --depth 1 https://github.com/nerfstudio-project/gsplat
  pip install -q -r gsplat/examples/requirements.txt
  echo "== Training (30k, data_factor 4) =="
  python gsplat/examples/simple_trainer.py default \
      --data_dir "$DATA" --data_factor 4 --max_steps 30000 \
      --result_dir /workspace/gsout --disable_viewer
  python - "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
out = sys.argv[1]
ck = sorted(glob.glob("/workspace/gsout/**/ckpts/*.pt", recursive=True))
assert ck, "kein gsplat-Checkpoint"
s = torch.load(ck[-1], map_location="cpu"); s = s.get("splats", s)
g = lambda k: s[k].detach().cpu().numpy()
means = g("means").astype(np.float32); N = means.shape[0]
fdc = g("sh0").astype(np.float32).reshape(N, 3)
frest = g("shN").astype(np.float32).transpose(0, 2, 1).reshape(N, -1)
cols = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2"] \
     + [f"f_rest_{i}" for i in range(frest.shape[1])] + ["opacity"] \
     + ["scale_0","scale_1","scale_2"] + ["rot_0","rot_1","rot_2","rot_3"]
data = np.concatenate([means, np.zeros((N,3),np.float32), fdc, frest,
    g("opacities").astype(np.float32).reshape(N,1), g("scales").astype(np.float32),
    g("quats").astype(np.float32)], axis=1).astype(np.float32)
el = np.empty(N, dtype=[(c,"f4") for c in cols])
for i,c in enumerate(cols): el[c] = data[:,i]
PlyData([PlyElement.describe(el,"vertex")]).write(out)
print(f"-> {out}  ({N:,} Gaussians)")
PY
fi

[ -f "$OUTPLY" ] || { echo "FEHLER: kein Ergebnis-PLY"; exit 1; }
echo "=========================================================="
echo " FERTIG -> $OUTPLY  ($(du -h "$OUTPLY" | cut -f1))"
echo " Herunterladen, dann Drag&Drop in https://playcanvas.com/supersplat/editor"
echo " Pod danach STOPPEN."
echo "=========================================================="
