#!/usr/bin/env bash
# Script de démarrage agnostique Railway/Render : les deux plateformes
# injectent PORT et lancent ce script (Railway) ou une commande équivalente
# (Render), sans jamais exiger de mode d'exécution spécifique à l'une des deux.
#
# --timeout 90 : couvre le pire cas du pipeline (jusqu'à 3 tentatives Claude à
# 20s + scraping ~3s = ~63s dans le pire des cas), avec marge au-dessus du
# timeout du module HTTP Make (60s, configuré côté Make). Ne jamais laisser ce
# timeout applicatif être le goulot le plus court de la chaîne.
set -euo pipefail

exec gunicorn --bind "0.0.0.0:${PORT:-8080}" --workers "${WEB_CONCURRENCY:-2}" --timeout 90 connectors.http_endpoint:app
