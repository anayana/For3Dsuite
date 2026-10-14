#!/usr/bin/env bash
# train_ipad_runpod.sh -- iPhone/iPad-LiDAR-Raumscan -> METRISCHER 3D-Gaussian-Splat
# auf einer gemieteten Linux-GPU (RunPod/vast.ai) oder jeder CUDA-Maschine.
#
# Aufnahme: App-Export als ZIP (3d Scanner App "All Data", Record3D "EXR + JPG",
# Polycam Raw Data oder transforms.json), optional ein ZIP mit hochaufgeloesten
# Fotos. Auf dem Pod NUR:
#
#   export CAPTURE_URL="https://.../scan.zip"      # Pflicht
#   export STILLS_URL="https://.../fotos.zip"      # optional
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/main/scripts/train_ipad_runpod.sh | bash
#
# oder mit Dateien, die schon auf dem Pod liegen:
#   bash train_ipad_runpod.sh /workspace/scan.zip [/workspace/fotos.zip]
#
# Ablauf: ipad_capture.py prepare (ARKit-Posen + LiDAR -> COLMAP, Messwolke,
# Raummasse) -> [Fotos: ipad_sfm.sh, PnP-Einhaengung in den metrischen Rahmen]
# -> gsplat mit LiDAR-Tiefen-Loss + Posen-Feinjustage -> metrischer Export ->
# viewer-fertige Verkleinerung -> ZIP-Upload. Am Ende steht eine URL.
#
# Empfohlener Pod: CUDA-*devel*-Vorlage, >= 16 GB VRAM (RTX A4000/3090/4090).
# Raum mit ~300 Keyframes: ~20-40 min Training. Fotos: + COLMAP auf der CPU.
#
# Stellschrauben (Umgebung): STEPS=30000  FACTOR=1  MAX_FRAMES=300  POSE_OPT=1
#   DEPTH_LAMBDA=0.01  KEEP=700000  NAME=raum  GSPLAT_REF=v1.5.3
#   F3D_REF=main (Branch, von dem die Hilfsskripte geladen werden)
set -euo pipefail

STEPS="${STEPS:-30000}"; FACTOR="${FACTOR:-1}"; MAX_FRAMES="${MAX_FRAMES:-300}"
POSE_OPT="${POSE_OPT:-1}"; DEPTH_LAMBDA="${DEPTH_LAMBDA:-0.01}"; KEEP="${KEEP:-700000}"
NAME="${NAME:-raum}"; GSPLAT_REF="${GSPLAT_REF:-v1.5.3}"; F3D_REF="${F3D_REF:-main}"
CAPTURE="${1:-${CAPTURE_URL:-}}"; STILLS="${2:-${STILLS_URL:-}}"
[ -n "$CAPTURE" ] || { echo "FEHLER: CAPTURE_URL setzen oder Pfad/URL als 1. Argument"; exit 1; }

echo "=========================================================="
echo " iPad-LiDAR -> metrischer 3DGS -- $(hostname)"
echo "=========================================================="
command -v nvidia-smi >/dev/null || { echo "FEHLER: keine GPU/nvidia-smi"; exit 1; }
nvidia-smi -L
need() { command -v "$1" >/dev/null || { apt-get update -qq && apt-get install -y -qq "${2:-$1}"; }; }
need git; need curl; need unzip; need zip

python - <<'PY'
import torch
print("torch      :", torch.__version__, "| CUDA", torch.version.cuda)
assert torch.cuda.is_available(), "torch sieht keine GPU"
cap = torch.cuda.get_device_capability(0)
print("GPU        :", torch.cuda.get_device_name(0), "-> CC", f"{cap[0]}.{cap[1]}")
open("/tmp/arch", "w").write(f"{cap[0]}.{cap[1]}")
PY
TORCH_CUDA_ARCH_LIST="$(cat /tmp/arch)"; export TORCH_CUDA_ARCH_LIST

WORK="${WORK:-/workspace/ipad}"; [ -d /workspace ] || WORK="${WORK/\/workspace/$HOME}"
mkdir -p "$WORK" && cd "$WORK"

# ---- Hilfsskripte: aus dem Repo-Checkout neben diesem Skript, sonst von GitHub ----
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
mkdir -p tools
for f in ipad_capture.py ipad_sfm.sh gsplat_export_metric.py ply_reduce.py; do
  if [ -n "$HERE" ] && [ -f "$HERE/$f" ]; then cp "$HERE/$f" tools/
  else curl -fsSL "https://raw.githubusercontent.com/anayana/For3Dsuite/$F3D_REF/scripts/$f" \
         -o "tools/$f" || { echo "FEHLER: $f nicht ladbar (F3D_REF=$F3D_REF?)"; exit 1; }
  fi
done

# ---- Eingaben holen (URL oder Pfad; ZIP oder Ordner) ----
fetch() {  # fetch <quelle> <zielordner>
  local src="$1" dst="$2"
  rm -rf "$dst"; mkdir -p "$dst"
  if [[ "$src" =~ ^https?:// ]]; then
    curl -fL "$src" -o "$dst.zip" || { echo "FEHLER: Download $src"; exit 1; }
    src="$dst.zip"
  fi
  if [ -d "$src" ]; then cp -r "$src"/. "$dst"/
  else unzip -oq "$src" -d "$dst" || { echo "FEHLER: $src ist kein ZIP"; exit 1; }
  fi
  rm -rf "$dst/__MACOSX"
}
echo "== Aufnahme holen =="
fetch "$CAPTURE" capture
STILL_ARG=()
if [ -n "$STILLS" ]; then
  echo "== Fotos holen =="
  fetch "$STILLS" stills_raw
  mkdir -p stills
  find stills_raw -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \
       -o -iname '*.heic' -o -iname '*.heif' \) -exec cp -t stills {} +
  echo "   $(ls stills | wc -l) Fotos"
  STILL_ARG=(--stills stills)
elif [ -d capture/stills ]; then
  STILL_ARG=(--stills capture/stills)            # Fotos im selben ZIP unter stills/
fi

python -c "import PIL" 2>/dev/null || pip install -q pillow
if [ ${#STILL_ARG[@]} -gt 0 ] && find "${STILL_ARG[1]}" -iname '*.hei[cf]' -print -quit | grep -q .; then
  python -c "import pillow_heif" 2>/dev/null || pip install -q pillow-heif
fi
if find capture -name '*.exr' -print -quit | grep -q .; then   # Record3D-Tiefe
  python -c "import cv2" 2>/dev/null || pip install -q "opencv-python-headless==4.10.0.84"
fi

echo "== Datensatz vorbereiten (ARKit-Posen + LiDAR) =="
python tools/ipad_capture.py prepare capture data --max-frames "$MAX_FRAMES" "${STILL_ARG[@]}"

if [ ${#STILL_ARG[@]} -gt 0 ]; then
  need colmap; need xvfb-run xvfb
  echo "== Fotos metrisch einhaengen (COLMAP) =="
  set +e; QT_QPA_PLATFORM=offscreen bash tools/ipad_sfm.sh data tools/ipad_capture.py; RC=$?; set -e
  [ "$RC" -eq 0 ] || echo "!! Fotos nicht eingehaengt (Code $RC) -- Training nur mit ARKit-Frames"
fi

# ---- gsplat (feste Version: Beispiele + Bibliothek passen zusammen) ----
echo "== gsplat $GSPLAT_REF =="
[ -d gsplat ] || git clone --recursive --depth 1 --branch "$GSPLAT_REF" \
  https://github.com/nerfstudio-project/gsplat
git -C gsplat submodule update --init --recursive
pip install -q ninja plyfile
export MAX_JOBS="${MAX_JOBS:-4}"          # nvcc sonst OOM-gekillt
pip install --no-build-isolation -r gsplat/examples/requirements.txt
python -c "import gsplat, sys; sys.exit(0 if gsplat.__version__.lstrip('v') == '${GSPLAT_REF#v}' else 1)" \
  2>/dev/null && echo "gsplat schon installiert" || pip install --no-build-isolation ./gsplat

if [ "$FACTOR" -gt 1 ] && [ ! -d "data/images_$FACTOR" ]; then
  python - "$FACTOR" <<'PY'
import os, sys
from PIL import Image
f = int(sys.argv[1]); src, dst = "data/images", f"data/images_{f}"
os.makedirs(dst, exist_ok=True)
for n in sorted(os.listdir(src)):
    im = Image.open(os.path.join(src, n)).convert("RGB")
    im.resize((im.width // f, im.height // f), Image.LANCZOS).save(os.path.join(dst, n), quality=95)
PY
fi

echo "== Training ($STEPS Schritte, LiDAR-Tiefen-Loss, Posen-Feinjustage=$POSE_OPT) =="
EXTRA=(--depth_loss --depth_lambda "$DEPTH_LAMBDA")
[ "$POSE_OPT" = "1" ] && EXTRA+=(--pose_opt)
rm -rf gsout
python gsplat/examples/simple_trainer.py default \
  --data_dir data --data_factor "$FACTOR" --max_steps "$STEPS" \
  --result_dir gsout --disable_viewer "${EXTRA[@]}"

echo "== Export in Metern (Normalisierung herausrechnen) =="
python tools/gsplat_export_metric.py gsout/ckpts data "${NAME}_full.ply" \
  --examples gsplat/examples --factor "$FACTOR"
python tools/ply_reduce.py "${NAME}_full.ply" "${NAME}_splat.ply" --keep "$KEEP"

mkdir -p result && rm -f result/* "${NAME}_ergebnis.zip"
cp "${NAME}_splat.ply" result/
cp data/lidar_points.ply "result/${NAME}_lidar_points.ply"
cp data/capture_report.json "result/${NAME}_bericht.json"
(cd result && zip -q "../${NAME}_ergebnis.zip" ./*)

python - "result/${NAME}_bericht.json" <<'PY'
import json, sys
r = json.load(open(sys.argv[1])); d = r["raummasse_naeherung"]
print(f"   Raum (Naeherung): {d['laenge_m']:.2f} x {d['breite_m']:.2f} m, Hoehe {d['hoehe_m']:.2f} m"
      f"  | Posen: {r['posen']} | {r['frames']} Frames + {r['stills']} Fotos")
PY
echo "== Upload =="
URL="$(curl -fsSL -F"file=@${NAME}_ergebnis.zip" https://0x0.st 2>/dev/null || true)"
echo "=========================================================="
echo " FERTIG.  $(pwd)/${NAME}_ergebnis.zip ($(du -h "${NAME}_ergebnis.zip" | cut -f1))"
echo "   ${NAME}_splat.ply          Splat in Metern (Viewer)"
echo "   ${NAME}_lidar_points.ply   Messwolke (CloudCompare: Messen)"
echo "   ${NAME}_bericht.json       Raummasse, Ausrichtung, Statistik"
if [ -n "$URL" ]; then echo; echo " >>> Download: $URL"
else echo; echo " Auto-Upload fehlgeschlagen -- ZIP per JupyterLab-Dateibrowser holen."; fi
UP="$(python -c "import json,sys; print(*json.load(open(sys.argv[1]))['up'])" "result/${NAME}_bericht.json")"
echo " Einhaengen in die Galerie (lokal):"
echo "   python platform/dev/seed_splat.py ${NAME}_splat.ply --id ${NAME} --title \"...\" --camera-up $UP"
echo "=========================================================="
