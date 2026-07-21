#!/usr/bin/env bash
# Holt TreeGrOSS (GPLv3) von der NW-FVA. Die Bibliothek wird bewusst NICHT im
# Repo mitgeliefert -- sie steht unter GPLv3 und bleibt als eigener Prozess/
# Klassenpfad isoliert (siehe ../README.md, Abschnitt GPL-Abgrenzung).
#
#   bash growth-service/lib/fetch_treegross.sh
#
# Ergebnis:
#   lib/dist/treegross.jar                     <- Laufzeit-JAR
#   lib/dist/lib/jep-2.4.1.jar                 <- Abhaengigkeit (Expression Parser)
#   lib/src/treegross/model/*.xml              <- Modell-/Artparametersaetze
#   lib/gpl-3.0.txt                            <- Lizenztext
set -euo pipefail

URL="https://nw-fva.de/fileadmin/nwfva/software/treegross.zip"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Lade TreeGrOSS von ${URL} ..."
curl -fSL -o "${DIR}/treegross.zip" "${URL}"

echo "Entpacke ..."
python -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" \
       "${DIR}/treegross.zip" "${DIR}"

test -f "${DIR}/dist/treegross.jar" || { echo "treegross.jar fehlt!" >&2; exit 1; }
echo "OK: $(ls -la "${DIR}/dist/treegross.jar" | awk '{print $5}') Bytes -> lib/dist/treegross.jar"
echo
echo "Modelldateien (fuer growth.treegross.model):"
ls "${DIR}/src/treegross/model/" | sed 's/^/  /'
echo
echo "WICHTIG: ein Modell mit voll qualifizierten Plugin-Namen waehlen, z. B."
echo "  ForestSimulatorNWGermany6.xml   (ForestSimulatorNWGermany.xml nennt die"
echo "  Plugins unqualifiziert -> ClassNotFoundException: Competition)"
