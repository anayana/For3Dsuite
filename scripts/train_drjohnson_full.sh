#!/usr/bin/env bash
# train_drjohnson_full.sh -- FULL-QUALITY 3D Gaussian Splatting von "Dr Johnson's
# House" (Deep-Blending-Datensatz). Unterschied zum Web-Skript:
#   * Training auf VOLLER Bildaufloesung (data_factor 1) statt halber
#   * Ergebnis-.ply mit ALLEN Gaussians + vollen Blickwinkel-Effekten (SH)  <-- scharfe Referenz
#   * zusaetzlich eine schaerfere Web-Version (mehr Gaussians)
#
# Du fuehrst NUR diesen einen Befehl auf dem Pod aus:
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_drjohnson_full.sh | bash
#
# Am Ende stehen ZWEI Download-Links (72 h gueltig):
#   1) drjohnson_full.ply  -> lokal in SuperSplat (supersplat.playcanvas.com) oeffnen = volle Qualitaet
#   2) drjohnson_web.ply    -> schickst du mir fuer die Galerie
#
# Empfohlener Pod: CUDA-Pod mit >=24 GB VRAM (RTX 3090/4090/A5000/A6000).
# Full-Res braucht mehr Speicher/Zeit als die Web-Version (~60-90 min).
set -euo pipefail

echo "=========================================================="
echo " Dr Johnson's House 3DGS -- FULL QUALITY -- $(hostname)"
echo "=========================================================="
command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU/nvidia-smi"; exit 1; }
nvidia-smi -L

command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
command -v curl >/dev/null || { apt-get update -qq && apt-get install -y -qq curl; }

python - <<'PY'
import torch
print("torch      :", torch.__version__)
print("CUDA(torch):", torch.version.cuda)
assert torch.cuda.is_available(), "torch sieht keine GPU"
cap = torch.cuda.get_device_capability(0)
print("GPU        :", torch.cuda.get_device_name(0), "-> CC", f"{cap[0]}.{cap[1]}")
open("/tmp/arch", "w").write(f"{cap[0]}.{cap[1]}")
PY
export TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"

# ---- Datensatz ----
cd /workspace 2>/dev/null || cd /root
if [ ! -d db/drjohnson/sparse ]; then
  echo "== Lade Deep-Blending-Datensatz (~660 MB) =="
  curl -fL "https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/datasets/input/tandt_db.zip" \
       -o tandt_db.zip || { echo "FEHLER: Datensatz-Download fehlgeschlagen"; exit 1; }
  python - <<'PY'
import zipfile; zipfile.ZipFile("tandt_db.zip").extractall("."); print("entpackt")
PY
fi
DATA="$(pwd)/db/drjohnson"
[ -d "$DATA/sparse" ] || DATA="$(dirname "$(find . -maxdepth 3 -path '*drjohnson/sparse' -type d | head -1)")"
NIMG=$(ls "$DATA/images/" 2>/dev/null | wc -l)
echo "Datensatz: $DATA | Bilder: $NIMG"
[ "$NIMG" -gt 50 ] || { echo "FEHLER: zu wenige Bilder in $DATA"; exit 1; }

# ---- gsplat aufsetzen ----
echo "== gsplat vorbereiten =="
[ -d gsplat ] || git clone --recursive --depth 1 https://github.com/nerfstudio-project/gsplat
git -C gsplat submodule update --init --recursive
export MAX_JOBS="${MAX_JOBS:-4}"
pip install -q ninja plyfile pillow
pip install --no-build-isolation -r gsplat/examples/requirements.txt
python -c "import gsplat.color_correct" 2>/dev/null \
  && echo "gsplat schon installiert -- Build uebersprungen" \
  || pip install --no-build-isolation ./gsplat

OUTPLY=/workspace/drjohnson_full.ply
[ -d /workspace ] || OUTPLY=/root/drjohnson_full.ply

# ---- Training auf VOLLER Aufloesung (data_factor 1 -> Ordner "images") ----
echo "== Training FULL-RES (data_factor 1, 30k) -- ~60-90 min =="
python gsplat/examples/simple_trainer.py default \
    --data_dir "$DATA" --data_factor 1 --max_steps 30000 \
    --result_dir /workspace/gsout_full --disable_viewer

echo "== Exportiere volle PLY (alle Gaussians + SH) =="
python - "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
out = sys.argv[1]
ck = sorted(glob.glob("/workspace/gsout_full/**/ckpts/*.pt", recursive=True))
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
print(f"-> {out} ({N:,} Gaussians, mit SH)")
PY
[ -f "$OUTPLY" ] || { echo "FEHLER: kein Ergebnis-PLY -- Log oben pruefen"; exit 1; }

# ---- schaerfere Web-Version (mehr Gaussians als bisher, Grundfarbe) ----
echo "== Web-Version verkleinern (1,2 Mio Gaussians) =="
curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/ply_reduce.py -o /tmp/ply_reduce.py
WEBPLY="$(dirname "$OUTPLY")/drjohnson_web.ply"
python /tmp/ply_reduce.py "$OUTPLY" "$WEBPLY" --keep 1200000

# ---- Uploads (litterbox: bis 1 GB, 72 h) ----
up(){ curl -fsSL -F "reqtype=fileupload" -F "time=72h" -F "fileToUpload=@$1" \
      "https://litterbox.catbox.moe/resources/internals/api.php" 2>/dev/null || true; }
echo "== Lade hoch (kann bei der vollen Datei dauern) =="
FULLURL="$(up "$OUTPLY")"
WEBURL="$(up "$WEBPLY")"

echo "=========================================================="
echo " FERTIG (FULL QUALITY)."
echo "   voll (SH):  $OUTPLY  ($(du -h "$OUTPLY" | cut -f1))"
echo "   web:        $WEBPLY  ($(du -h "$WEBPLY" | cut -f1))"
echo ""
if [ -n "$FULLURL" ]; then
  echo " >>> VOLLE QUALITAET (in SuperSplat oeffnen): $FULLURL"
else
  echo " Upload der vollen Datei fehlgeschlagen -- per JupyterLab herunterladen: $OUTPLY"
fi
if [ -n "$WEBURL" ]; then
  echo " >>> WEB-VERSION (schick mir diese URL): $WEBURL"
else
  echo " Web-Upload fehlgeschlagen -- $WEBPLY per JupyterLab herunterladen."
fi
echo "=========================================================="
