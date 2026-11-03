#!/usr/bin/env bash
# pellis_batch.sh -- mehrere Pellis-Gebaeude nacheinander auf EINEM RunPod-Pod rechnen.
# Im Pod-Terminal (JupyterLab -> Terminal) einfuegen; laeuft im Hintergrund weiter, auch wenn der
# Browser zu ist:
#
#   curl -fsSL https://raw.githubusercontent.com/anayana/For3Dsuite/<SHA>/scripts/pellis_batch.sh | S=<SHA> bash
#
# Ergebnisse: /workspace/ERGEBNISSE.txt (auch im Pod-Log). Fertig, wenn dort PELLIS-RUN-ENDE steht.
# Danach Pod loeschen.
S="${S:?S (Commit) fehlt}"
BUILDINGS="${BUILDINGS:-3_SS 2_OSA}"
nohup bash -c '
  out() { tee -a /workspace/ERGEBNISSE.txt > /proc/1/fd/1 2>/dev/null || tee -a /workspace/ERGEBNISSE.txt; }
  mkdir -p /workspace/pellis
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq aria2 >/dev/null)
  for B in '"$BUILDINGS"'; do
    date -u +"START $B %H:%M" | out
    aria2c -x 8 -s 8 -k 20M --file-allocation=none --console-log-level=warn --summary-interval=0 \
      --show-console-readout=false -c -d /workspace/pellis -o "$B.rar" \
      "https://zenodo.org/records/14626611/files/$B.rar?download=1"
    curl -fsSL "https://raw.githubusercontent.com/anayana/For3Dsuite/'"$S"'/scripts/train_pellis_runpod.sh" \
      | BRANCH='"$S"' FORCE=1 STEPS=30000 UNDIST=0 TEST_EVERY=1000 bash -s -- "$B" > "/workspace/run_$B.log" 2>&1
    grep -E "Fotos:|PSNR|FEHLER|Error|Label|Referenz|Gaussians" "/workspace/run_$B.log" | sed "s/^/ERGEBNIS $B /" | out
    tail -3 "/workspace/run_$B.log" | sed "s/^/LOGENDE $B /" | out
    date -u +"FERTIG $B %H:%M" | out
    rm -rf "/workspace/pellis/$B.rar" "/workspace/pellis/raw_$B" /workspace/pellis/${B}_*
  done
  echo PELLIS-RUN-ENDE | out
' > /workspace/batch.log 2>&1 &
echo "Laeuft im Hintergrund (Gebaeude: $BUILDINGS). Fortschritt: tail -f /workspace/batch.log ; Ergebnisse: cat /workspace/ERGEBNISSE.txt"
