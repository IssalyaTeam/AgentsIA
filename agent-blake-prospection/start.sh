#!/usr/bin/env bash
# Script de démarrage agnostique Railway/Render : les deux plateformes
# injectent PORT et lancent ce script (Railway) ou une commande équivalente
# (Render), sans jamais exiger de mode d'exécution spécifique à l'une des deux.
set -euo pipefail

exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers "${WEB_CONCURRENCY:-2}" --timeout 30 connectors.http_endpoint:app
