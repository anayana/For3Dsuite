#!/usr/bin/env bash
# arkitscenes_fetch.sh -- eine echte iPad-Pro-LiDAR-Aufnahme aus Apples freiem
# Datensatz ARKitScenes holen, im Layout, das ipad_capture.py (Format
# "arkitscenes") direkt liest. Ideal zum Testen ohne eigenen Scan.
#
#   bash scripts/arkitscenes_fetch.sh [video_id] [zielordner]
#   python scripts/ipad_capture.py prepare arkitscenes_41069021 raum_daten
#
# Geholt wird (grob geschaetzt 0,5-2 GB je Aufnahme):
#   - Upsampling-Teil: color/ (1920x1440), lowres_depth/ + confidence/ (iPad-LiDAR),
#     highres_depth/ (Tiefe aus dem Faro-Laserscanner = Referenz fuer die Genauigkeit)
#   - RAW-Teil: lowres_wide.traj (ARKit-Posen), lowres_wide_intrinsics/
# Aufnahmen ausserhalb des Upsampling-Teils: vga_wide/ (640x480) statt color/,
# ohne Laserscanner-Referenz.
#
# Lizenz: ARKitScenes ist nur fuer NICHT-kommerzielle Zwecke freigegeben
# (siehe github.com/apple/ARKitScenes, LICENSE). Quelle nennen: Baruch et al.,
# "ARKitScenes", NeurIPS 2021 Datasets and Benchmarks.
set -euo pipefail
VID="${1:-41069021}"
DST="${2:-arkitscenes_$VID}"
BASE="https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"
GH="https://raw.githubusercontent.com/apple/ARKitScenes/main"
need() { command -v "$1" >/dev/null || { echo "FEHLER: $1 fehlt"; exit 1; }; }
need curl; need unzip

fold() {  # fold <csv-url> -> Training/Validation (leer, wenn nicht enthalten)
  # erst ganz laden: bei "curl | awk ... exit" bricht curl mit Code 23 ab,
  # und pipefail beendet das Skript
  local csv
  csv="$(curl -fsSL "$1")" || { echo "FEHLER: $1 nicht ladbar" >&2; return 1; }
  awk -F, -v v="$VID" '$1 == v { print $3; exit }' <<< "$csv"
}
UPS="$(fold "$GH/depth_upsampling/upsampling_train_val_splits.csv")"
RAW="$(fold "$GH/raw/raw_train_val_splits.csv")"
[ -n "$RAW" ] || { echo "FEHLER: video_id $VID nicht im RAW-Teil von ARKitScenes"; exit 1; }

mkdir -p "$DST"
DST="$(cd "$DST" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

get() {  # get <url> <datei>
  echo "   $1"
  curl -fL --retry 3 "$1" -o "$2" || { echo "FEHLER: Download $1"; exit 1; }
}
take_dir() {  # take_dir <zip> <ordnername>: Ordner mit diesem Namen aus dem ZIP uebernehmen
  local x="$TMP/x_$2"
  rm -rf "$x"; mkdir -p "$x"; unzip -q "$1" -d "$x"
  local d
  d="$(find "$x" -type d -name "$2" | head -1)"
  if [ -z "$d" ]; then d="$x"; fi                  # ZIP ohne Unterordner
  rm -rf "${DST:?}/$2"; mv "$d" "$DST/$2"
}

echo "== ARKitScenes $VID (RAW: $RAW${UPS:+, Upsampling: $UPS}) -> $DST =="
get "$BASE/raw/$RAW/$VID/lowres_wide.traj" "$DST/lowres_wide.traj"
get "$BASE/raw/$RAW/$VID/lowres_wide_intrinsics.zip" "$TMP/intr.zip"
take_dir "$TMP/intr.zip" lowres_wide_intrinsics

if [ -n "$UPS" ]; then
  get "$BASE/upsampling/$UPS/$VID.zip" "$TMP/ups.zip"
  mkdir -p "$TMP/ups" && unzip -q "$TMP/ups.zip" -d "$TMP/ups"
  echo "   Inhalt des Upsampling-ZIPs:"
  (cd "$TMP/ups" && find . -maxdepth 3 -type d | sort | sed 's/^/     /')
  # Apples README nennt den Bildordner "color", Archive koennen "wide" heissen
  for d in color wide highres_depth lowres_depth confidence; do
    src="$(find "$TMP/ups" -type d -name "$d" | head -1)"
    if [ -n "$src" ]; then rm -rf "${DST:?}/$d"; mv "$src" "$DST/$d"; fi
  done
  [ -d "$DST/color" ] || [ -d "$DST/wide" ] \
    || { echo "FEHLER: kein Bildordner (color/ oder wide/) im Upsampling-ZIP"; exit 1; }
else
  echo "   (nicht im Upsampling-Teil: VGA-Bilder, keine Laserscanner-Referenz)"
  for a in lowres_depth confidence vga_wide vga_wide_intrinsics; do
    get "$BASE/raw/$RAW/$VID/$a.zip" "$TMP/$a.zip"
    take_dir "$TMP/$a.zip" "$a"
  done
fi
echo "== fertig: $(find "$DST" -name '*.png' | wc -l) Bilder =="
echo "   python scripts/ipad_capture.py prepare \"$DST\" raum_daten"
