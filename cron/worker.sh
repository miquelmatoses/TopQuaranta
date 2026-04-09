#!/bin/bash

LOCKFILE="/tmp/worker.lock"

# Evita duplicats
if [ -e "$LOCKFILE" ]; then
    echo "Ja s'està executant, eixint..."
    exit 0
fi
touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

# Exportar PATH perquè cron no el carrega per defecte
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Navegar a la carpeta arrel del projecte
cd /root/TopQuaranta

# Carregar variables d'entorn
set -a
. .env
set +a

# Activar entorn virtual
source venv/bin/activate

# Executar worker amb timeout de 24h
timeout 3540 /root/TopQuaranta/venv/bin/python3 scripts/worker.py
