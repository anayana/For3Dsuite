#!/usr/bin/env bash
# Einmalige Garage-Initialisierung auf dem Server (aus platform/ heraus aufrufen):
#   bash init/bootstrap.sh
# Legt Layout, Buckets (media oeffentlich, originals privat) und den App-Key an.
set -euo pipefail
cd "$(dirname "$0")/.."

# Das rpc_secret gehoert in die NICHT versionierte platform/.env, nicht in
# garage/garage.toml -- sonst wandert es beim naechsten Commit ins Repository.
if [ ! -f .env ] || ! grep -q '^GARAGE_RPC_SECRET=..' .env; then
  SECRET=$(openssl rand -hex 32)
  echo "GARAGE_RPC_SECRET=$SECRET" >> .env
  echo "==> GARAGE_RPC_SECRET erzeugt und an platform/.env angehaengt."
fi

docker compose up -d garage
echo "==> Warte auf Garage ..."
sleep 5

g() { docker compose exec -T garage /garage "$@"; }

NODE=$(g node id -q | cut -d@ -f1)
echo "==> Node: $NODE"
g layout assign -z dc1 -c 100G "$NODE" || true
g layout apply --version 1 || echo "   (Layout evtl. schon aktiv)"

g bucket create media 2>/dev/null || echo "   Bucket media existiert schon."
g bucket create originals 2>/dev/null || echo "   Bucket originals existiert schon."
g bucket website --allow media

if KEYINFO=$(g key create pano-app 2>/dev/null); then
  KEY_ID=$(echo "$KEYINFO" | awk '/Key ID/{print $NF}')
  KEY_SECRET=$(echo "$KEYINFO" | awk '/Secret key/{print $NF}')
  echo
  echo "==> In platform/.env eintragen:"
  echo "S3_ACCESS_KEY=$KEY_ID"
  echo "S3_SECRET_KEY=$KEY_SECRET"
else
  echo "   Key pano-app existiert schon (Secret ist nur bei Erzeugung sichtbar)."
fi

g bucket allow --read --write --owner media --key pano-app
g bucket allow --read --write --owner originals --key pano-app

echo
echo "==> Fertig. Danach: .env ausfuellen und 'docker compose up -d --build' starten."
