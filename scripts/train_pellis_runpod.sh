#!/usr/bin/env bash
# train_pellis_runpod.sh -- 3D Gaussian Splatting fuer ein Gebaeude des Pellis-Datensatzes
# (Zenodo 14626611, CC BY 4.0) auf einer gemieteten RunPod-GPU, ein Befehl:
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/claude/for3dsuite-medien-marker-1ihant/scripts/train_pellis_runpod.sh | bash -s -- 5_CB
#
# Ablauf: RAR laden (aria2c, mehrere Verbindungen) + md5 -> entpacken -> pellis_to_colmap.py
# (Fotos entzerren, Posen ins System der Punktwolke, Initwolke) -> Posenprobe (Abbruch, wenn
# die Punktwolke nicht zu den Fotos passt) -> gsplat 1.5.3 -> PLY im System der Punktwolke
# -> eval_splat_geometry.py. Ergebnisse unter /workspace/pellis/<Gebaeude>_*.
#
# Umgebung: Template mit CUDA-devel (nvcc), z. B. RunPod "PyTorch 2.x"; Disk >= 50 GB.
# Variablen: STEPS (30000), FACTOR (2 = halbe Aufloesung), FORCE=1 (Posenprobe ignorieren).
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
command -v aria2c >/dev/null || NEED="$NEED aria2"
command -v unrar  >/dev/null || NEED="$NEED unrar"
command -v git    >/dev/null || NEED="$NEED git"
if [ -n "$NEED" ]; then
  echo "installiere:$NEED"
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $NEED >/dev/null) \
    || { echo "FEHLER: apt-get install$NEED fehlgeschlagen"; exit 1; }
fi

# ---- Laden + pruefen -------------------------------------------------------
RAR="$W/$B.rar"
URL="https://zenodo.org/records/14626611/files/$B.rar?download=1"
if [ -f "$RAR" ] && [ "$(md5sum "$RAR" | cut -d' ' -f1)" = "${MD5[$B]}" ]; then
  echo "$B.rar schon da, md5 ok"
else
  echo "== Lade $B.rar (aria2c, 8 Verbindungen) =="
  aria2c -x 8 -s 8 -k 20M --file-allocation=none --summary-interval=60 \
         --console-log-level=warn -c -d "$W" -o "$B.rar" "$URL"
  GOT="$(md5sum "$RAR" | cut -d' ' -f1)"
  [ "$GOT" = "${MD5[$B]}" ] || { echo "FEHLER: md5 $GOT, erwartet ${MD5[$B]}"; exit 1; }
  echo "md5 ok"
fi

echo "== Entpacke =="
mkdir -p "$W/raw_$B"
unrar x -o+ -idq "$RAR" "$W/raw_$B/"
INT="$(find "$W/raw_$B" -name '*interior_parameters.txt' | head -1)"
EXT="$(find "$W/raw_$B" -name '*exterior_parameters.txt' | head -1)"
TRF="$(find "$W/raw_$B" -name '*transformation_matrix.txt' | head -1)"
PCL="$(find "$W/raw_$B" -name '*point_cloud.txt' | head -1)"
FIRST="$(find "$W/raw_$B" -iname "${B}_001.*" | head -1)"
for v in INT EXT TRF PCL FIRST; do
  [ -n "${!v}" ] || { echo "FEHLER: $v nicht gefunden"; find "$W/raw_$B" -maxdepth 3 | head -40; exit 1; }
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

# ---- Posenprobe: Farbe der Initpunkte gegen Fotopixel -----------------------
echo "== Posenprobe =="
python - "$DATA" <<'PY'
import os, sys, struct, numpy as np, cv2
d = sys.argv[1]; sp = os.path.join(d, "sparse", "0")
cam = open(os.path.join(sp, "cameras.txt")).read().splitlines()[1].split()
W, H, fx, fy, cx, cy = int(cam[2]), int(cam[3]), *map(float, cam[4:8])
pts = np.array([[float(v) for v in l.split()[1:7]] for l in open(os.path.join(sp, "points3D.txt"))
                if l.strip() and not l.startswith("#")])
xyz, rgb = pts[:, :3], pts[:, 3:6]
gray_p = rgb @ [0.299, 0.587, 0.114]
rows = [l.split() for l in open(os.path.join(sp, "images.txt")) if l.strip() and not l.startswith("#")]
def q2R(w, x, y, z):
    return np.array([[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
                     [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
                     [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]])
cors = []
for r in rows[:: max(1, len(rows) // 8)][:8]:
    R = q2R(*map(float, r[1:5])); t = np.array(list(map(float, r[5:8])))
    Xc = xyz @ R.T + t; z = Xc[:, 2]
    u = fx * Xc[:, 0] / np.maximum(z, 1e-6) + cx; v = fy * Xc[:, 1] / np.maximum(z, 1e-6) + cy
    m = (z > 0.1) & (u >= 0) & (u < W - 1) & (v >= 0) & (v < H - 1)
    img = cv2.imread(os.path.join(d, "images", r[9]), cv2.IMREAD_GRAYSCALE)
    if m.sum() < 200 or img is None:
        print(f"  {r[9]}: {m.sum()} Punkte im Bild -- uebersprungen"); continue
    g_img = img[v[m].astype(int), u[m].astype(int)].astype(float)
    c = np.corrcoef(g_img, gray_p[m])[0, 1]
    # Gegenprobe: Bild um 200 px verschoben -> Korrelation muss deutlich fallen
    us = np.clip(u[m] + 200, 0, W - 1).astype(int)
    c0 = np.corrcoef(img[v[m].astype(int), us].astype(float), gray_p[m])[0, 1]
    cors.append(c)
    print(f"  {r[9]}: {m.sum():>7} Punkte im Bild, Korrelation {c:.2f} (verschoben {c0:.2f})")
med = float(np.median(cors)) if cors else 0.0
print(f"  Median-Korrelation {med:.2f}")
open("/tmp/posenprobe", "w").write(f"{med:.3f}")
PY
MED="$(cat /tmp/posenprobe)"
if python -c "import sys; sys.exit(0 if float('$MED') >= 0.3 else 1)"; then
  echo "Posenprobe ok ($MED)"
elif [ "${FORCE:-0}" = "1" ]; then
  echo "WARNUNG: Posenprobe schwach ($MED), FORCE=1 -> weiter"
else
  echo "FEHLER: Posenprobe schwach ($MED) -- Punktwolke passt nicht zu den Fotos. Abbruch vor dem Training."
  exit 1
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
