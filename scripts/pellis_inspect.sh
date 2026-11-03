#!/usr/bin/env bash
# pellis_inspect.sh -- Pellis-Datensatz (Zenodo 14626611, CC BY 4.0): Inhalt von
# 5_CB.rar auflisten, ohne zu entpacken. Laeuft im RunPod-Web-Terminal (auch ohne GPU).
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/claude/for3dsuite-medien-marker-1ihant/scripts/pellis_inspect.sh | bash
set -euo pipefail

DIR=${DIR:-/workspace/pellis}
mkdir -p "$DIR" && cd "$DIR"
df -h "$DIR" | tail -1

if ! command -v unrar >/dev/null; then
  (apt-get update -qq && apt-get install -y -qq unrar) \
    || (apt-get install -y -qq unrar-free) \
    || { echo "FEHLER: unrar nicht installierbar"; exit 1; }
fi

[ -f 5_CB.rar ] || wget -q -O 5_CB.rar "https://zenodo.org/records/14626611/files/5_CB.rar?download=1"
echo "md5 erwartet: 1814a907a649ef500ee90e19679615d1"
md5sum 5_CB.rar

echo "--- Dateitypen ---"
unrar lb 5_CB.rar | sed -n 's/.*\.//p' | sort | uniq -c | sort -rn
echo "--- erste 60 Eintraege ---"
unrar lb 5_CB.rar | head -60
