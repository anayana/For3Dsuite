#!/usr/bin/env bash
# pellis_pod.sh -- Startbefehl eines RunPod-Pods fuer ein Pellis-Gebaeude.
# Liegt das Ergebnis schon auf dem Volume, wird es nur ausgegeben; sonst Zenodo-Archiv laden und
# train_pellis_runpod.sh laufen lassen. Danach haelt der Pod sich SOFORT selbst an (GPU-Kosten enden);
# das Ergebnis bleibt in /workspace/ERGEBNIS_<Gebaeude>.txt und wird beim naechsten Start nur ausgegeben.
#
#   curl -fsSL .../<SHA>/scripts/pellis_pod.sh | B=3_SS S=<SHA> STEPS=30000 UNDIST=0 TEST_EVERY=1000 bash
B="${B:?B fehlt}"
S="${S:?S (Commit) fehlt}"
R="/workspace/ERGEBNIS_$B.txt"
if [ ! -s "$R" ]; then
  date -u +'START %H:%M'
  mkdir -p /workspace/pellis
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq aria2 >/dev/null)
  aria2c -x 8 -s 8 -k 20M --file-allocation=none --console-log-level=warn --summary-interval=0 \
    --show-console-readout=false -c -d /workspace/pellis -o "$B.rar" \
    "https://zenodo.org/records/14626611/files/$B.rar?download=1"
  date -u +'DOWNLOAD-ENDE %H:%M'
  curl -fsSL "https://raw.githubusercontent.com/anayana/For3Dsuite/$S/scripts/train_pellis_runpod.sh" \
    | BRANCH="$S" FORCE=1 bash -s -- "$B" > "/workspace/run_$B.log" 2>&1
  {
    echo "EXIT $?"
    grep -E 'Fotos:|PSNR|FEHLER|Error|Label|Referenz|Gaussians|Training \(|Posenprobe|Variante' \
      "/workspace/run_$B.log" | tail -30 | sed 's/^/ERGEBNIS /'
    tail -6 "/workspace/run_$B.log" | sed 's/^/LOGENDE /'
    date -u +'FERTIG %H:%M'
  } > "$R"
fi
cat "$R"
echo PELLIS-RUN-ENDE
runpodctl stop pod "$RUNPOD_POD_ID"
sleep infinity
