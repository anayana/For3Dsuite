#!/usr/bin/env bash
# train_petra_runpod.sh -- 3D Gaussian Splatting von "Petra - Treasury Face"
# (Al-Khazneh) aus dem CULTURE3D-Datensatz. Die CULTURE3D-Freigabe enthaelt nur
# Bilder + RealityCapture (proprietaer), KEIN COLMAP -> die Posen rechnen wir hier
# mit COLMAP selbst, dann trainieren wir 3DGS mit gsplat.
#
# Du fuehrst NUR diesen einen Befehl auf dem Pod aus:
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_petra_runpod.sh | bash
#
# Empfohlener Pod: CUDA-Pod mit >=24 GB VRAM (RTX 3090/4090/A5000). COLMAP + 3DGS
# zusammen ~1-1.5 h. Am Ende steht eine Download-URL -- die schickst du mir.
#
# Attribution: CULTURE3D (Zheng et al., ICCV 2025). Nur Forschungs-/Demo-Nutzung.
set -euo pipefail

IMAGES_URL="https://files.catbox.moe/uo567o.zip"   # wird vor dem Commit eingesetzt (verkleinerte Bilder, ~1600 px)

echo "=========================================================="
echo " Petra (Treasury Face) 3DGS -- $(hostname)"
echo "=========================================================="
command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU"; exit 1; }
nvidia-smi -L
command -v git  >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
command -v curl >/dev/null || { apt-get update -qq && apt-get install -y -qq curl; }
command -v unzip>/dev/null || { apt-get update -qq && apt-get install -y -qq unzip; }

cd /workspace 2>/dev/null || cd /root
mkdir -p petra && cd petra
DATA="$(pwd)"

# ---- Bilder holen (verkleinert) ----
if [ ! -d images ] || [ -z "$(ls -A images 2>/dev/null)" ]; then
  echo "== Lade Bilder =="
  curl -fL "$IMAGES_URL" -o images.zip || { echo "FEHLER: Bild-Download"; exit 1; }
  mkdir -p images && cd images && unzip -oq ../images.zip && cd ..
  # flach ziehen, falls in Unterordner entpackt
  find images -mindepth 2 -type f \( -iname '*.jpg' -o -iname '*.png' \) -exec mv -t images {} + 2>/dev/null || true
  find images -type d -empty -delete 2>/dev/null || true
fi
NIMG=$(find images -maxdepth 1 -type f | wc -l); echo "Bilder: $NIMG"
[ "$NIMG" -gt 30 ] || { echo "FEHLER: zu wenige Bilder"; exit 1; }

# ---- COLMAP: Posen rechnen ----
command -v colmap >/dev/null || { echo "== installiere COLMAP =="; apt-get update -qq && apt-get install -y -qq colmap; }
# GPU-SIFT braucht einen OpenGL-Display -> auf headless Pods per xvfb bereitstellen
# (sonst Qt-"abort"). Mit virtuellem Display laeuft die GPU-Extraktion sauber & schnell.
command -v xvfb-run >/dev/null || { apt-get update -qq && apt-get install -y -qq xvfb; }
GPUCOL="xvfb-run -a colmap"
if [ ! -d sparse/0 ]; then
  echo "== COLMAP: Feature-Extraktion (GPU via xvfb) =="
  rm -f database.db
  $GPUCOL feature_extractor --database_path database.db --image_path images \
    --ImageReader.single_camera 1 --ImageReader.camera_model OPENCV \
    --SiftExtraction.use_gpu 1 || \
  colmap feature_extractor --database_path database.db --image_path images \
    --ImageReader.single_camera 1 --ImageReader.camera_model OPENCV \
    --SiftExtraction.use_gpu 0 --SiftExtraction.num_threads 8
  echo "== COLMAP: Matching (exhaustive, GPU via xvfb) =="
  $GPUCOL exhaustive_matcher --database_path database.db --SiftMatching.use_gpu 1 || \
  colmap exhaustive_matcher --database_path database.db --SiftMatching.use_gpu 0
  echo "== COLMAP: Mapper (kann dauern) =="
  mkdir -p sparse
  colmap mapper --database_path database.db --image_path images --output_path sparse
fi
[ -d sparse/0 ] || { echo "FEHLER: COLMAP hat keine Rekonstruktion erzeugt (sparse/0 fehlt)"; exit 1; }
echo "COLMAP fertig: $(ls sparse)"

# ---- gsplat aufsetzen (baut kein diff_gaussian_rasterization) ----
python - <<'PY'
import torch
open("/tmp/arch","w").write("%d.%d"%torch.cuda.get_device_capability(0))
print("torch",torch.__version__,"CUDA",torch.version.cuda,torch.cuda.get_device_name(0))
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"; export MAX_JOBS="${MAX_JOBS:-4}"
cd /workspace 2>/dev/null || cd /root
[ -d gsplat ] || git clone --recursive --depth 1 https://github.com/nerfstudio-project/gsplat
git -C gsplat submodule update --init --recursive
pip install -q ninja plyfile pillow
pip install --no-build-isolation -r gsplat/examples/requirements.txt
python -c "import gsplat.color_correct" 2>/dev/null \
  && echo "gsplat schon installiert -- Build uebersprungen" \
  || pip install --no-build-isolation ./gsplat

OUTPLY=/workspace/petra_gaussians.ply
[ -d /workspace ] || OUTPLY=/root/petra_gaussians.ply

echo "== Training (30k) -- ~30-45 min =="
python gsplat/examples/simple_trainer.py default \
    --data_dir "$DATA" --data_factor 1 --max_steps 30000 \
    --result_dir /workspace/petra_out --disable_viewer

echo "== Exportiere volle PLY (mit SH) =="
python - "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
out=sys.argv[1]
ck=sorted(glob.glob("/workspace/petra_out/**/ckpts/*.pt",recursive=True)); assert ck,"kein Checkpoint"
s=torch.load(ck[-1],map_location="cpu"); s=s.get("splats",s)
g=lambda k:s[k].detach().cpu().numpy()
means=g("means").astype(np.float32); N=means.shape[0]
scales=g("scales").astype(np.float32); quats=g("quats").astype(np.float32)
opac=g("opacities").astype(np.float32).reshape(N,1)
fdc=g("sh0").astype(np.float32).reshape(N,3)
frest=g("shN").astype(np.float32).transpose(0,2,1).reshape(N,-1)
cols=["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2"]+[f"f_rest_{i}" for i in range(frest.shape[1])]+["opacity"]+["scale_0","scale_1","scale_2"]+["rot_0","rot_1","rot_2","rot_3"]
data=np.concatenate([means,np.zeros((N,3),np.float32),fdc,frest,opac,scales,quats],1).astype(np.float32)
el=np.empty(N,dtype=[(c,"f4") for c in cols])
for i,c in enumerate(cols): el[c]=data[:,i]
PlyData([PlyElement.describe(el,"vertex")]).write(out); print("->",out,N,"Gaussians")
PY
[ -f "$OUTPLY" ] || { echo "FEHLER: kein Ergebnis-PLY"; exit 1; }

echo "== Web-Version verkleinern (1,2 Mio) =="
curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/ply_reduce.py -o /tmp/ply_reduce.py
WEBPLY=/workspace/petra_web.ply
python /tmp/ply_reduce.py "$OUTPLY" "$WEBPLY" --keep 1200000

echo "== Upload (litterbox, 72h) =="
up(){ curl -fsSL -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@$1" "https://litterbox.catbox.moe/resources/internals/api.php" 2>/dev/null || true; }
WEBURL="$(up "$WEBPLY")"; FULLURL="$(up "$OUTPLY")"
echo "=========================================================="
echo " FERTIG."
echo "   voll: $OUTPLY ($(du -h "$OUTPLY"|cut -f1))  web: $WEBPLY ($(du -h "$WEBPLY"|cut -f1))"
[ -n "$WEBURL" ] && echo " >>> WEB-VERSION (schick mir diese URL): $WEBURL" || echo " Web-Upload fehlgeschlagen -> $WEBPLY per JupyterLab laden"
[ -n "$FULLURL" ] && echo " >>> VOLL (optional, SuperSplat): $FULLURL"
echo "=========================================================="
