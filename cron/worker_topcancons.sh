#!/bin/bash

LOCKFILE="/tmp/worker_update_topcancons.lock"

# Evita duplicats
if [ -e "$LOCKFILE" ]; then
    echo "Ja s'està executant, ixint..."
    exit 0
fi
touch "$LOCKFILE"
trap "rm -f $LOCKFILE" EXIT

# Exportar PATH perquè cron no el carrega per defecte
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Navegar a la carpeta arrel del projecte
cd /root/TopQuaranta

# Carregar variables d'entorn del .env
set -a
. .env
set +a

# Activar l'entorn virtual
source venv/bin/activate

# Executar l’script principal amb timeout
timeout 180 /root/TopQuaranta/venv/bin/python3 /root/TopQuaranta/scripts/worker_update_top_cancons.py
