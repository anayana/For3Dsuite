#!/usr/bin/env bash
# train_pellis_runpod.sh -- 3D Gaussian Splatting fuer ein Gebaeude des Pellis-Datensatzes
# (Zenodo 14626611, CC BY 4.0) auf einer gemieteten RunPod-GPU, ein Befehl:
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/claude/for3dsuite-medien-marker-1ihant/scripts/train_pellis_runpod.sh | bash -s -- 5_CB
#
# KEIN Download auf dem Pod (Nutzer-Anweisung): <Gebaeude>.rar muss schon unter
# /workspace/pellis/ liegen (vom Nutzer hochgeladen). Ablauf: md5 -> entpacken -> pellis_to_colmap.py
# (Fotos entzerren, Posen ins System der Punktwolke, Initwolke) -> Posenprobe (Abbruch, wenn
# die Punktwolke nicht zu den Fotos passt) -> gsplat 1.5.3 -> PLY im System der Punktwolke
# -> eval_splat_geometry.py. Ergebnisse unter /workspace/pellis/<Gebaeude>_*.
#
# Umgebung: Template mit CUDA-devel (nvcc), z. B. RunPod "PyTorch 2.x"; Disk >= 50 GB.
# Variablen: STEPS (30000), FACTOR (2 = halbe Aufloesung), FORCE=1 (Posenprobe ignorieren),
#            SRC=<ordner> (lose hochgeladene Dateien statt RAR).
set -euo pipefail

B="${1:-5_CB}"
BRANCH="${BRANCH:-claude/for3dsuite-medien-marker-1ihant}"
RAW="https://raw.githubusercontent.com/anayana/For3Dsuite/$BRANCH/scripts"
STEPS="${STEPS:-30000}"
FACTOR="${FACTOR:-2}"
W=/workspace/pellis
mkdir -p "$W" && cd "$W"

declare -A MD5=(
  [1_SC]=a41d08054beb7b1675fbadaa2abafd9f [2_OSA]=6d8eb0a68339d17935c0039dca961f25
  [3_SS]=42d55c23c4c5ec148b8b045826b0fb14 [4_CG]=0a0c3576e1a233651dff36e92873ad04
  [5_CB]=1814a907a649ef500ee90e19679615d1 )
[ -n "${MD5[$B]:-}" ] || { echo "FEHLER: unbekanntes Gebaeude '$B' (1_SC 2_OSA 3_SS 4_CG 5_CB)"; exit 1; }

echo "=========================================================="
echo " Pellis $B -- 3DGS auf $(hostname), $(date -u +%H:%M) UTC"
echo "=========================================================="
command -v nvidia-smi >/dev/null && nvidia-smi -L || { echo "FEHLER: keine GPU"; exit 1; }
df -h "$W" | tail -1

# ---- Werkzeuge -------------------------------------------------------------
NEED=""
command -v unrar  >/dev/null || NEED="$NEED unrar"
command -v git    >/dev/null || NEED="$NEED git"
if [ -n "$NEED" ]; then
  echo "installiere:$NEED"
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $NEED >/dev/null) \
    || { echo "FEHLER: apt-get install$NEED fehlgeschlagen"; exit 1; }
fi

# ---- Daten: entweder <Gebaeude>.rar (wird entpackt) oder lose Dateien in SRC ----------
# SRC=/workspace: Nutzer hat Fotos, Parameter- und Punktwolkendatei einzeln hochgeladen.
RAR="$W/$B.rar"
EXCL=()
if [ -n "${SRC:-}" ]; then
  RAWDIR="$SRC"
  EXCL=(-not -path "$W/*")          # eigene Arbeitsdateien unter $W nicht mitfinden
  echo "Daten lose in $RAWDIR (kein Archiv)"
else
  [ -f "$RAR" ] || { echo "FEHLER: $RAR fehlt -- bitte hochladen (kein Download auf dem Pod)"; exit 1; }
  GOT="$(md5sum "$RAR" | cut -d' ' -f1)"
  [ "$GOT" = "${MD5[$B]}" ] || { echo "FEHLER: md5 $GOT, erwartet ${MD5[$B]}"; exit 1; }
  echo "$B.rar md5 ok"
  echo "== Entpacke =="
  RAWDIR="$W/raw_$B"
  mkdir -p "$RAWDIR"
  unrar x -o+ -idq "$RAR" "$RAWDIR/"
fi
INT="$(find "$RAWDIR" "${EXCL[@]}" -name '*interior_parameters.txt' | head -1)"
EXT="$(find "$RAWDIR" "${EXCL[@]}" -name '*exterior_parameters.txt' | head -1)"
TRF="$(find "$RAWDIR" "${EXCL[@]}" -name '*transformation_matrix.txt' | head -1)"
PCL="$(find "$RAWDIR" "${EXCL[@]}" -name '*point_cloud.txt' | head -1)"
FIRST="$(find "$RAWDIR" "${EXCL[@]}" -iname "${B}_001.*" | head -1)"
for v in INT EXT TRF PCL FIRST; do
  [ -n "${!v}" ] || { echo "FEHLER: $v nicht gefunden"; find "$RAWDIR" -maxdepth 3 | head -40; exit 1; }
  echo "  $v = ${!v}"
done
IMGDIR="$(dirname "$FIRST")"
echo "  Fotos: $(ls "$IMGDIR" | wc -l) in $IMGDIR"
echo "  Punktwolke, erste Zeilen:"; head -3 "$PCL"

# ---- gsplat 1.5.3 (vor dem Wandler: legt numpy<2 fest) ---------------------
echo "== gsplat 1.5.3 =="
cd "$W"
[ -d gsplat ] || git clone -q --depth 1 --branch v1.5.3 https://github.com/nerfstudio-project/gsplat
pip install -q gsplat==1.5.3 plyfile
pip install -q -r gsplat/examples/requirements.txt
pip install -q "numpy<2" opencv-python-headless scipy

# ---- COLMAP-Modell ---------------------------------------------------------
echo "== pellis_to_colmap =="
curl -fsSL "$RAW/pellis_to_colmap.py"   -o "$W/pellis_to_colmap.py"
curl -fsSL "$RAW/eval_splat_geometry.py" -o "$W/eval_splat_geometry.py"
DATA="$W/${B}_colmap"
rm -rf "$DATA"
python "$W/pellis_to_colmap.py" "$INT" "$EXT" "$DATA" --transform "$TRF" --cloud "$PCL" \
       --images "$IMGDIR"
NIMG=$(ls "$DATA/images" | wc -l)
[ "$NIMG" -gt 20 ] || { echo "FEHLER: nur $NIMG Fotos im Modell"; exit 1; }

# ---- Posenprobe: welche Konvention passt zu Fotos + Punktwolke? ------------------
echo "== Posenprobe (4 Varianten, Tiefenpuffer) =="
curl -fsSL "$RAW/pellis_posecheck.py" -o "$W/pellis_posecheck.py"
if python "$W/pellis_posecheck.py" "$INT" "$EXT" "$TRF" "$DATA/sparse/0/points3D.txt" \
          "$DATA/images" --out /tmp/posenflags; then
  echo "Posenprobe ok"
elif [ "${FORCE:-0}" = "1" ]; then
  echo "WARNUNG: Posenprobe nicht eindeutig, FORCE=1 -> weiter"
else
  echo "FEHLER: Posenprobe nicht eindeutig -- Abbruch vor dem Training."
  exit 1
fi
FLAGS="$(cat /tmp/posenflags)"
if [ -n "$FLAGS" ]; then
  echo "== pellis_to_colmap erneut mit $FLAGS =="
  rm -rf "$DATA"
  # shellcheck disable=SC2086
  python "$W/pellis_to_colmap.py" "$INT" "$EXT" "$DATA" --transform "$TRF" --cloud "$PCL" \
         --images "$IMGDIR" $FLAGS
fi

# gsplat erwartet images_<FACTOR>; als PNG anlegen (dann wird nichts erneut verkleinert)
if [ "$FACTOR" -gt 1 ]; then
  python - "$DATA" "$FACTOR" <<'PY'
import os, sys, cv2
d, f = sys.argv[1], int(sys.argv[2])
src, dst = os.path.join(d, "images"), os.path.join(d, f"images_{f}")
os.makedirs(dst, exist_ok=True)
for n in sorted(os.listdir(src)):
    im = cv2.imread(os.path.join(src, n))
    h, w = im.shape[:2]
    cv2.imwrite(os.path.join(dst, os.path.splitext(n)[0] + ".png"),
                cv2.resize(im, (round(w / f), round(h / f)), interpolation=cv2.INTER_AREA))
print(f"images_{f}: {len(os.listdir(dst))} PNG")
PY
fi

# ---- Training --------------------------------------------------------------
echo "== Training ($STEPS Schritte, Faktor $FACTOR), $(date -u +%H:%M) UTC =="
GS="$W/${B}_gs"
python gsplat/examples/simple_trainer.py default \
    --data_dir "$DATA" --data_factor "$FACTOR" --max_steps "$STEPS" \
    --result_dir "$GS" --disable_viewer
ls "$GS/stats" 2>/dev/null && cat "$GS"/stats/val_step*.json 2>/dev/null | tail -c 600 || true

# ---- Export im System der Punktwolke ---------------------------------------
echo "== Export PLY (gsplat-Normierung rueckgaengig) =="
OUTPLY="$W/${B}_gaussians.ply"
cd "$W/gsplat/examples"
python - "$DATA" "$FACTOR" "$GS" "$OUTPLY" <<'PY'
import sys, glob, numpy as np, torch
from plyfile import PlyData, PlyElement
from datasets.colmap import Parser
data, factor, gs, out = sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4]
T = Parser(data_dir=data, factor=factor, normalize=True, test_every=8).transform  # Welt -> normiert
A, t = T[:3, :3], T[:3, 3]
s = np.cbrt(np.linalg.det(A)); Rn = A / s
ck = sorted(glob.glob(f"{gs}/ckpts/*.pt"), key=lambda p: int(p.split("_")[-2]))
st = torch.load(ck[-1], map_location="cpu")["splats"]
g = lambda k: st[k].detach().cpu().numpy().astype(np.float64)
means = (g("means") - t) @ Rn / s                     # = Rn^T (x - t) / s
scales = g("scales") - np.log(s)                       # log-Skalen
q = g("quats"); q /= np.linalg.norm(q, axis=1, keepdims=True)
# Rotation der Gauss-Ellipsoide: R_welt = Rn^T R_norm  -> Quaternion links mit conj(q_Rn) multiplizieren
def mat2quat(M):
    w = np.sqrt(max(0.0, 1 + M[0,0] + M[1,1] + M[2,2])) / 2
    x = np.copysign(np.sqrt(max(0.0, 1 + M[0,0] - M[1,1] - M[2,2])) / 2, M[2,1] - M[1,2])
    y = np.copysign(np.sqrt(max(0.0, 1 - M[0,0] + M[1,1] - M[2,2])) / 2, M[0,2] - M[2,0])
    z = np.copysign(np.sqrt(max(0.0, 1 - M[0,0] - M[1,1] + M[2,2])) / 2, M[1,0] - M[0,1])
    return np.array([w, x, y, z])
a = mat2quat(Rn.T)
w1, x1, y1, z1 = a; w2, x2, y2, z2 = q.T
quats = np.stack([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2,
                  w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2], 1)
N = len(means)
fdc = g("sh0").reshape(N, 3); frest = g("shN").transpose(0, 2, 1).reshape(N, -1)
cols = (["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2"]
        + [f"f_rest_{i}" for i in range(frest.shape[1])]
        + ["opacity","scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"])
arr = np.concatenate([means, np.zeros((N, 3)), fdc, frest, g("opacities").reshape(N, 1),
                      scales, quats], 1).astype(np.float32)
el = np.empty(N, dtype=[(c, "f4") for c in cols])
for i, c in enumerate(cols):
    el[c] = arr[:, i]
PlyData([PlyElement.describe(el, "vertex")]).write(out)
print(f"-> {out} ({N:,} Gaussians), Normierung s={s:.4f}, Zentren min {means.min(0).round(2)} max {means.max(0).round(2)}")
PY
cd "$W"

# ---- Geometrie gegen Referenz ----------------------------------------------
echo "== Geometrie-Pruefung =="
python "$W/eval_splat_geometry.py" "$OUTPLY" "$PCL" --out "$W/${B}_geometrie.json"

echo "=========================================================="
echo " FERTIG $(date -u +%H:%M) UTC"
echo "  PLY:       $OUTPLY ($(du -h "$OUTPLY" | cut -f1))"
echo "  Geometrie: $W/${B}_geometrie.json"
echo "  Kennzahlen gsplat: $GS/stats/"
echo "=========================================================="
