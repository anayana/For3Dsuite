#!/usr/bin/env bash
# For3Dsuite CPU-Container -- Einstiegspunkte:
#   serve       (Default) Reproduktion, dann statische Gallery/Viewer aus docs/ auf :8000
#   reproduce   nur der reproduzierbare Offline-Lauf auf committeten Daten
#   check       Reproduktion + Plausibilitaetspruefung, Fehlercode bei Problemen (CI)
#   <sonst>     als Befehl ausfuehren (z. B. python scripts/inventory_from_cloud.py ...)
set -euo pipefail

# Pfade GROSS/klein exakt wie im Repo: unter Windows ist das Dateisystem
# unempfindlich, im Linux-Container nicht -- "data/renon" fand hier nichts.
STAND_CSV="data/Renon/trees_setup001.csv"
STAND_CFG="data/Renon/renon_stand.json"

reproduce() {
  echo "== Reproduktion: Wuchsprognose aus committeten Renon-Daten (offline) =="
  for f in "$STAND_CSV" "$STAND_CFG"; do
    if [ ! -f "$f" ]; then
      echo "FEHLER: $f fehlt im Image." >&2
      echo "        Vermutlich schliesst .dockerignore data/ zu weit aus." >&2
      return 1
    fi
  done
  # kein GPU, kein Netz, kein GPL-JAR -- nur der Python-Demonstrator (spiegelt
  # die Java-StubGrowthEngine); die echte TreeGrOSS-Engine siehe growth-service/.
  python scripts/treegross_export.py export \
      --csv "$STAND_CSV" --out /tmp/trees.json \
      --stand-config "$STAND_CFG" --years 20 --step 5
  python scripts/treegross_export.py simulate \
      /tmp/trees.json /tmp/future.json --base-year 2024
  # Ergebnis PRUEFEN statt nur "ok" zu melden: eine leere oder stehende
  # Prognose ist kein gelungener Lauf.
  python - <<'PY'
import json, sys
d = json.load(open("/tmp/future.json"))
p = d.get("periods") or []
if not p or not p[0].get("trees"):
    sys.exit("Ergebnis enthaelt keine Perioden/Baeume")
f = {t["id"]: t for t in p[0]["trees"]}
l = {t["id"]: t for t in p[-1]["trees"]}
d0 = sum(f[i]["dbh_cm"] for i in f) / len(f)
d1 = sum(l[i]["dbh_cm"] for i in l) / len(l)
print(f"   {len(f)} Baeume, {p[0]['year']}..{p[-1]['year']}: "
      f"mittlerer BHD {d0:.1f} -> {d1:.1f} cm")
if d1 <= d0:
    sys.exit("Kein Zuwachs -- Ergebnis unplausibel")
PY
  echo "== Reproduktion ok. Ergebnis: /tmp/future.json =="
}

case "${1:-serve}" in
  serve)
    # NICHT 'reproduce || echo ...': in einer ||-Verkettung schaltet bash das
    # 'set -e' INNERHALB der Funktion ab. Dadurch lief sie nach dem ersten
    # Fehler weiter und meldete am Ende "Reproduktion ok", obwohl beide
    # Schritte gescheitert waren -- ein falsches Gruen. Der Serverbetrieb soll
    # trotzdem nicht am Datenfehler haengen, also abfangen und klar benennen.
    if reproduce; then :; else
      echo "!! Reproduktion FEHLGESCHLAGEN -- der Server startet trotzdem." >&2
    fi
    echo "== Gallery/Viewer auf http://localhost:8000/  (Strg+C zum Beenden) =="
    exec python -m http.server 8000 --directory docs ;;
  reproduce)
    reproduce ;;
  check)
    reproduce
    echo "== check ok ==" ;;
  *)
    exec "$@" ;;
esac
