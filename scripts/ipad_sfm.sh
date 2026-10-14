#!/usr/bin/env bash
# ipad_sfm.sh -- hochaufgeloeste Fotos metrisch in eine iPad-Aufnahme einhaengen.
#
#   bash scripts/ipad_sfm.sh <datensatz> [pfad/zu/ipad_capture.py]
#
# <datensatz> kommt von "ipad_capture.py prepare ... --stills <ordner>".
# Kein freies SfM: freie Rekonstruktionen driften im Massstab (in Raeumen mit
# vielen Drehungen und kurzen Wegen typisch). Stattdessen:
#   1. SIFT-Merkmale fuer Frames und Fotos, Matching
#   2. point_triangulator mit den FESTEN ARKit-Posen -> metrische 3D-Merkmale
#   3. image_registrator: Fotos per PnP auf diese Merkmale -> Fotoposen in Metern
#   4. "ipad_capture.py refine": Kontrolle (Massstab ~1) + Datensatz mit Fotos
# Scheitert etwas, bleibt sparse/0 mit den ARKit-Frames unveraendert (Exit 2).
#
# Umgebung: COLMAP_GPU=1 (SIFT auf der GPU; CUDA-COLMAP oder xvfb),
#           MATCHER=exhaustive|sequential (Default: exhaustive bis 400 Bilder).
set -euo pipefail
DATA="$(cd "$1" && pwd)"
TOOL="$(cd "$(dirname "${2:-$0}")" && pwd)/$(basename "${2:-ipad_capture.py}")"
GPU="${COLMAP_GPU:-0}"
COLMAP="colmap"
if [ "$GPU" = "1" ] && command -v xvfb-run >/dev/null; then COLMAP="xvfb-run -a colmap"; fi

cd "$DATA"
NF=$(grep -c . frames.txt || true); NS=$(grep -c . stills.txt || true)
[ "$NS" -gt 0 ] || { echo "Keine Fotos (stills.txt leer) -- nichts zu tun."; exit 0; }
echo "== Fotos einhaengen: $NF Frames + $NS Fotos =="
rm -rf database.db colmap_known colmap_tri colmap_reg colmap_txt
mkdir -p colmap_known colmap_tri colmap_reg colmap_txt
# zwei Laeufe -> Frames und Fotos bekommen je EINE eigene Kamera
$COLMAP feature_extractor --database_path database.db --image_path images \
  --image_list_path frames.txt --ImageReader.single_camera 1 \
  --ImageReader.camera_model PINHOLE --SiftExtraction.use_gpu "$GPU" \
  --SiftExtraction.max_num_features 4096
$COLMAP feature_extractor --database_path database.db --image_path images \
  --image_list_path stills.txt --ImageReader.single_camera 1 \
  --ImageReader.camera_model OPENCV --SiftExtraction.use_gpu "$GPU" \
  --SiftExtraction.max_num_features 8192
MATCHER="${MATCHER:-$([ $((NF + NS)) -le 400 ] && echo exhaustive || echo sequential)}"
echo "== Matching: $MATCHER =="
if [ "$MATCHER" = "sequential" ]; then
  # Frames sind zeitlich sortiert (f_00000 ...); Fotos haengen am Ende der Liste
  $COLMAP sequential_matcher --database_path database.db \
    --SiftMatching.use_gpu "$GPU" --SequentialMatching.overlap 30 \
    --SequentialMatching.quadratic_overlap 1
else
  $COLMAP exhaustive_matcher --database_path database.db --SiftMatching.use_gpu "$GPU"
fi
echo "== Triangulation mit festen ARKit-Posen =="
python "$TOOL" known "$DATA" database.db colmap_known
colmap point_triangulator --database_path database.db --image_path images \
  --input_path colmap_known --output_path colmap_tri \
  || { echo "!! Triangulation gescheitert -- es bleibt bei den ARKit-Frames"; exit 2; }
echo "== Fotos registrieren (PnP) =="
colmap image_registrator --database_path database.db \
  --input_path colmap_tri --output_path colmap_reg \
  || { echo "!! Registrierung gescheitert -- es bleibt bei den ARKit-Frames"; exit 2; }
colmap model_converter --input_path colmap_reg --output_path colmap_txt --output_type TXT
echo "== Kontrolle + Datensatz mit Fotos =="
python "$TOOL" refine "$DATA" colmap_txt \
  || { echo "!! Kontrolle nicht bestanden -- es bleibt bei den ARKit-Frames"; exit 2; }
