#!/usr/bin/env bash
# For3Dsuite CPU-Container -- Einstiegspunkte:
#   serve       (Default) statische Gallery/Viewer aus docs/ auf :8000
#   reproduce   reproduzierbarer Offline-Lauf auf committeten Daten, dann serve
#   <sonst>     als Befehl ausfuehren (z. B. python scripts/inventory_from_cloud.py ...)
set -euo pipefail

reproduce() {
  echo "== Reproduktion: Wuchsprognose aus committeten Renon-Daten (offline) =="
  # kein GPU, kein Netz, kein GPL-JAR -- nur der Python-Demonstrator (spiegelt
  # die Java-StubGrowthEngine); die echte TreeGrOSS-Engine siehe growth-service/.
  python scripts/treegross_export.py export \
      --csv data/renon/trees_setup001.csv --out /tmp/trees.json \
      --stand-config data/renon/renon_stand.json --years 20 --step 5
  python scripts/treegross_export.py simulate \
      /tmp/trees.json /tmp/future.json --base-year 2024
  echo "== Reproduktion ok. Ergebnis: /tmp/future.json =="
}

case "${1:-serve}" in
  serve)
    reproduce || echo "(Reproduktion uebersprungen)"
    echo "== Gallery/Viewer auf http://localhost:8000/  (Strg+C zum Beenden) =="
    exec python -m http.server 8000 --directory docs ;;
  reproduce)
    reproduce ;;
  *)
    exec "$@" ;;
esac
